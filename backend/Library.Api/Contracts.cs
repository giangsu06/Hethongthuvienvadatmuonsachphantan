using Library.Core;

namespace Library.Api;

public sealed record BookResponse(
    string Id,
    string Title,
    string Author,
    string Category,
    string Isbn,
    int Total,
    int Available,
    bool Featured)
{
    public static BookResponse From(Book book) => new(
        book.Id, book.Title, book.Author, book.Category, book.Isbn,
        book.TotalCopies, book.AvailableCopies, book.Featured);
}

public sealed record ReservationResponse(
    Guid Id,
    string BookId,
    string UserId,
    string UserName,
    ReservationStatus Status,
    DateTimeOffset CreatedAt,
    DateTimeOffset? ProcessedAt,
    DateTimeOffset? BorrowedAt,
    DateTimeOffset? ReturnedAt,
    string? Reason)
{
    public static ReservationResponse From(Reservation reservation) => new(
        reservation.Id, reservation.BookId, reservation.UserId, reservation.UserName,
        reservation.Status, reservation.CreatedAt, reservation.ProcessedAt,
        reservation.BorrowedAt, reservation.ReturnedAt, reservation.Reason);
}

public sealed record CreateReservationRequest(string BookId, string UserId, string UserName);