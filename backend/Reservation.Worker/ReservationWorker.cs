using System.Text;
using System.Text.Json;
using Library.Core;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;

public sealed class ReservationWorker(
    IServiceScopeFactory scopeFactory,
    IOptions<RabbitSettings> settings,
    ILogger<ReservationWorker> logger) : BackgroundService
{
    private const string QueueName = "library.reservations";

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await ConsumeAsync(stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception exception)
            {
                logger.LogError(exception, "Reservation worker cannot reach RabbitMQ; retrying shortly.");
                await Task.Delay(TimeSpan.FromSeconds(5), stoppingToken);
            }
        }
    }

    private async Task ConsumeAsync(CancellationToken cancellationToken)
    {
        var factory = new ConnectionFactory
        {
            HostName = settings.Value.Host,
            UserName = settings.Value.User,
            Password = settings.Value.Password,
            DispatchConsumersAsync = true
        };
        using var connection = factory.CreateConnection();
        using var channel = connection.CreateModel();
        channel.QueueDeclare(QueueName, durable: true, exclusive: false, autoDelete: false);
        channel.BasicQos(0, 1, false);

        var consumer = new AsyncEventingBasicConsumer(channel);
        consumer.Received += async (_, delivery) =>
        {
            try
            {
                var message = JsonSerializer.Deserialize<ReservationRequested>(Encoding.UTF8.GetString(delivery.Body.Span));
                if (message is null) throw new InvalidDataException("Invalid reservation message.");
                await ProcessAsync(message.ReservationId, cancellationToken);
                channel.BasicAck(delivery.DeliveryTag, multiple: false);
            }
            catch (Exception exception)
            {
                logger.LogError(exception, "Reservation message could not be processed.");
                channel.BasicNack(delivery.DeliveryTag, multiple: false, requeue: true);
            }
        };
        channel.BasicConsume(QueueName, autoAck: false, consumer);
        logger.LogInformation("Reservation worker is consuming {QueueName}.", QueueName);
        await Task.Delay(Timeout.InfiniteTimeSpan, cancellationToken);
    }

    private async Task ProcessAsync(Guid reservationId, CancellationToken cancellationToken)
    {
        await using var scope = scopeFactory.CreateAsyncScope();
        var db = scope.ServiceProvider.GetRequiredService<LibraryDbContext>();
        await using var transaction = await db.Database.BeginTransactionAsync(cancellationToken);
        var reservation = await db.Reservations.SingleOrDefaultAsync(item => item.Id == reservationId, cancellationToken);
        if (reservation is null || reservation.Status != ReservationStatus.Pending)
        {
            await transaction.CommitAsync(cancellationToken);
            return;
        }

        var reserved = await db.Books
            .Where(book => book.Id == reservation.BookId && book.AvailableCopies > 0)
            .ExecuteUpdateAsync(update => update.SetProperty(book => book.AvailableCopies, book => book.AvailableCopies - 1), cancellationToken);
        reservation.Status = reserved == 1 ? ReservationStatus.Reserved : ReservationStatus.Rejected;
        reservation.ProcessedAt = DateTimeOffset.UtcNow;
        reservation.Reason = reserved == 1 ? null : "Sách hiện đã được đặt hết.";
        await db.SaveChangesAsync(cancellationToken);
        await transaction.CommitAsync(cancellationToken);
        logger.LogInformation("Reservation {ReservationId} processed as {Status}.", reservation.Id, reservation.Status);
    }
}