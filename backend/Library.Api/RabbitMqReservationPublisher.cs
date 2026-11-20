using System.Text;
using System.Text.Json;
using Library.Core;
using RabbitMQ.Client;

namespace Library.Api;

public sealed class RabbitMqReservationPublisher(IConfiguration configuration)
{
    private const string QueueName = "library.reservations";

    public Task PublishAsync(Guid reservationId, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var factory = new ConnectionFactory
        {
            HostName = configuration["RabbitMQ:Host"] ?? "localhost",
            UserName = configuration["RabbitMQ:User"] ?? "guest",
            Password = configuration["RabbitMQ:Password"] ?? "guest",
            RequestedConnectionTimeout = TimeSpan.FromSeconds(3),
            AutomaticRecoveryEnabled = false
        };

        using var connection = factory.CreateConnection();
        using var channel = connection.CreateModel();
        channel.QueueDeclare(QueueName, durable: true, exclusive: false, autoDelete: false);
        var body = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(new ReservationRequested(reservationId)));
        var properties = channel.CreateBasicProperties();
        properties.Persistent = true;
        channel.BasicPublish(exchange: "", routingKey: QueueName, basicProperties: properties, body: body);
        return Task.CompletedTask;
    }
}