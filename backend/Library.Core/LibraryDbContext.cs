using Microsoft.EntityFrameworkCore;

namespace Library.Core;

public enum ReservationStatus
{
    Pending,
    Reserved,
    Rejected,
    Borrowed,
    Returned
}

public sealed class Book
{
    public required string Id { get; set; }
    public required string Title { get; set; }
    public required string Author { get; set; }
    public required string Category { get; set; }
    public required string Isbn { get; set; }
    public int TotalCopies { get; set; }
    public int AvailableCopies { get; set; }
    public bool Featured { get; set; }
}

public sealed class LibraryUser
{
    public required string Id { get; set; }
    public required string Name { get; set; }
}

public sealed class Reservation
{
    public Guid Id { get; set; }
    public required string BookId { get; set; }
    public required string UserId { get; set; }
    public required string UserName { get; set; }
    public ReservationStatus Status { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset? ProcessedAt { get; set; }
    public DateTimeOffset? BorrowedAt { get; set; }
    public DateTimeOffset? ReturnedAt { get; set; }
    public string? Reason { get; set; }
}

public sealed class LibraryDbContext(DbContextOptions<LibraryDbContext> options) : DbContext(options)
{
    public DbSet<Book> Books => Set<Book>();
    public DbSet<LibraryUser> Users => Set<LibraryUser>();
    public DbSet<Reservation> Reservations => Set<Reservation>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Book>().HasKey(book => book.Id);
        modelBuilder.Entity<Book>().Property(book => book.Title).HasMaxLength(200);
        modelBuilder.Entity<Book>().Property(book => book.Author).HasMaxLength(160);
        modelBuilder.Entity<LibraryUser>().HasKey(user => user.Id);
        modelBuilder.Entity<Reservation>().HasKey(reservation => reservation.Id);
        modelBuilder.Entity<Reservation>().Property(reservation => reservation.Status).HasConversion<string>();
        modelBuilder.Entity<Reservation>().HasIndex(reservation => reservation.UserId);
    }
}

public sealed record ReservationRequested(Guid ReservationId);