using System.Text.Json.Serialization;
using Library.Api;
using Library.Core;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);
var databasePath = Path.GetFullPath(Path.Combine(builder.Environment.ContentRootPath, "..", "data", "library.db"));
Directory.CreateDirectory(Path.GetDirectoryName(databasePath)!);

builder.Services.AddDbContext<LibraryDbContext>(options => options.UseSqlite($"Data Source={databasePath}"));
builder.Services.AddSingleton<RabbitMqReservationPublisher>();
builder.Services.ConfigureHttpJsonOptions(options => options.SerializerOptions.Converters.Add(new JsonStringEnumConverter()));
builder.Services.AddCors(options => options.AddDefaultPolicy(policy => policy.AllowAnyOrigin().AllowAnyHeader().AllowAnyMethod()));
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();
app.UseCors();
app.UseSwagger();
app.UseSwaggerUI();

await using (var scope = app.Services.CreateAsyncScope())
{
    var db = scope.ServiceProvider.GetRequiredService<LibraryDbContext>();
    await db.Database.EnsureCreatedAsync();
    if (!await db.Books.AnyAsync())
    {
        db.Books.AddRange(
            new Book { Id = "BK001", Title = "Nhà giả kim", Author = "Paulo Coelho", Category = "Văn học", Isbn = "9786043444919", TotalCopies = 5, AvailableCopies = 5, Featured = true },
            new Book { Id = "BK002", Title = "Rừng Na Uy", Author = "Haruki Murakami", Category = "Văn học", Isbn = "9786041139481", TotalCopies = 4, AvailableCopies = 4, Featured = true },
            new Book { Id = "BK003", Title = "Sapiens: Lược sử loài người", Author = "Yuval Noah Harari", Category = "Lịch sử", Isbn = "9786041055294", TotalCopies = 6, AvailableCopies = 6, Featured = true },
            new Book { Id = "BK004", Title = "Đi tìm lẽ sống", Author = "Viktor E. Frankl", Category = "Tâm lý", Isbn = "9786041160562", TotalCopies = 4, AvailableCopies = 4, Featured = true },
            new Book { Id = "BK005", Title = "Tuổi trẻ đáng giá bao nhiêu", Author = "Rosie Nguyễn", Category = "Kỹ năng", Isbn = "9786041108695", TotalCopies = 5, AvailableCopies = 5 },
            new Book { Id = "BK006", Title = "Đắc nhân tâm", Author = "Dale Carnegie", Category = "Kỹ năng", Isbn = "9786041191339", TotalCopies = 7, AvailableCopies = 7 },
            new Book { Id = "BK007", Title = "Cây cam ngọt của tôi", Author = "José Mauro de Vasconcelos", Category = "Văn học", Isbn = "9786041161682", TotalCopies = 4, AvailableCopies = 4 },
            new Book { Id = "BK008", Title = "Tư duy nhanh và chậm", Author = "Daniel Kahneman", Category = "Tâm lý", Isbn = "9786041192190", TotalCopies = 3, AvailableCopies = 3 },
            new Book { Id = "BK009", Title = "Lược sử thời gian", Author = "Stephen Hawking", Category = "Khoa học", Isbn = "9786041120278", TotalCopies = 3, AvailableCopies = 3 },
            new Book { Id = "BK010", Title = "Bố già", Author = "Mario Puzo", Category = "Văn học", Isbn = "9786041189900", TotalCopies = 5, AvailableCopies = 5 },
            new Book { Id = "BK011", Title = "Muôn kiếp nhân sinh", Author = "Nguyên Phong", Category = "Tâm linh", Isbn = "9786041194262", TotalCopies = 4, AvailableCopies = 4 },
            new Book { Id = "BK012", Title = "Không gia đình", Author = "Hector Malot", Category = "Văn học", Isbn = "9786041127208", TotalCopies = 4, AvailableCopies = 4 });
        await db.SaveChangesAsync();
    }
}

app.MapGet("/health", () => TypedResults.Ok(new { status = "ok" }));
app.MapGet("/books", async (LibraryDbContext db, CancellationToken cancellationToken) =>
    TypedResults.Ok((await db.Books.AsNoTracking().OrderBy(book => book.Title).ToArrayAsync(cancellationToken)).Select(BookResponse.From)));
app.MapGet("/books/{id}", async (string id, LibraryDbContext db, CancellationToken cancellationToken) =>
{
    var book = await db.Books.AsNoTracking().SingleOrDefaultAsync(item => item.Id == id, cancellationToken);
    return book is null ? Results.NotFound() : Results.Ok(BookResponse.From(book));
}).WithName("GetBook");
app.MapGet("/reservations/{id:guid}", async (Guid id, LibraryDbContext db, CancellationToken cancellationToken) =>
{
    var reservation = await db.Reservations.AsNoTracking().SingleOrDefaultAsync(item => item.Id == id, cancellationToken);
    return reservation is null ? Results.NotFound() : Results.Ok(ReservationResponse.From(reservation));
}).WithName("GetReservation");
app.MapGet("/users/{userId}/reservations", async (string userId, LibraryDbContext db, CancellationToken cancellationToken) =>
    TypedResults.Ok((await db.Reservations.AsNoTracking()
        .Where(reservation => reservation.UserId == userId)
        .ToArrayAsync(cancellationToken))
        .OrderByDescending(reservation => reservation.CreatedAt)
        .Select(ReservationResponse.From)));
app.MapPost("/reservations", async (CreateReservationRequest request, LibraryDbContext db, RabbitMqReservationPublisher publisher, CancellationToken cancellationToken) =>
{
    if (string.IsNullOrWhiteSpace(request.BookId) || string.IsNullOrWhiteSpace(request.UserId) || string.IsNullOrWhiteSpace(request.UserName))
        return Results.ValidationProblem(new Dictionary<string, string[]> { ["request"] = ["Mã sách, mã bạn đọc và tên bạn đọc là bắt buộc."] });

    var bookExists = await db.Books.AnyAsync(book => book.Id == request.BookId, cancellationToken);
    if (!bookExists) return Results.NotFound();

    var user = await db.Users.SingleOrDefaultAsync(item => item.Id == request.UserId, cancellationToken);
    if (user is null) db.Users.Add(new LibraryUser { Id = request.UserId.Trim(), Name = request.UserName.Trim() });
    else user.Name = request.UserName.Trim();

    var reservation = new Reservation
    {
        Id = Guid.NewGuid(),
        BookId = request.BookId.Trim(),
        UserId = request.UserId.Trim(),
        UserName = request.UserName.Trim(),
        Status = ReservationStatus.Pending,
        CreatedAt = DateTimeOffset.UtcNow
    };
    db.Reservations.Add(reservation);
    await db.SaveChangesAsync(cancellationToken);
    try
    {
        await publisher.PublishAsync(reservation.Id, cancellationToken);
    }
    catch (Exception exception) when (exception is not OperationCanceledException)
    {
        db.Reservations.Remove(reservation);
        await db.SaveChangesAsync(cancellationToken);
        return Results.Problem("Không thể kết nối hàng đợi RabbitMQ. Hãy thử lại sau.", statusCode: StatusCodes.Status503ServiceUnavailable);
    }

    return Results.Created($"/reservations/{reservation.Id}", ReservationResponse.From(reservation));
}).WithName("CreateReservation");
app.MapPatch("/reservations/{id:guid}/borrow", async (Guid id, LibraryDbContext db, CancellationToken cancellationToken) =>
{
    var reservation = await db.Reservations.SingleOrDefaultAsync(item => item.Id == id, cancellationToken);
    if (reservation is null) return Results.NotFound();
    if (reservation.Status != ReservationStatus.Reserved) return Results.Conflict(new { message = "Chỉ yêu cầu đã giữ sách mới có thể nhận sách." });
    reservation.Status = ReservationStatus.Borrowed;
    reservation.BorrowedAt = DateTimeOffset.UtcNow;
    await db.SaveChangesAsync(cancellationToken);
    return Results.Ok(ReservationResponse.From(reservation));
}).WithName("BorrowReservation");
app.MapPatch("/reservations/{id:guid}/return", async (Guid id, LibraryDbContext db, CancellationToken cancellationToken) =>
{
    await using var transaction = await db.Database.BeginTransactionAsync(cancellationToken);
    var reservation = await db.Reservations.SingleOrDefaultAsync(item => item.Id == id, cancellationToken);
    if (reservation is null) return Results.NotFound();
    if (reservation.Status != ReservationStatus.Borrowed) return Results.Conflict(new { message = "Chỉ sách đang mượn mới có thể trả." });
    reservation.Status = ReservationStatus.Returned;
    reservation.ReturnedAt = DateTimeOffset.UtcNow;
    var book = await db.Books.SingleAsync(item => item.Id == reservation.BookId, cancellationToken);
    book.AvailableCopies = Math.Min(book.TotalCopies, book.AvailableCopies + 1);
    await db.SaveChangesAsync(cancellationToken);
    await transaction.CommitAsync(cancellationToken);
    return Results.Ok(ReservationResponse.From(reservation));
}).WithName("ReturnReservation");

app.Run();