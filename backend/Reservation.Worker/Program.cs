using Library.Core;
using Microsoft.EntityFrameworkCore;

var builder = Host.CreateApplicationBuilder(args);
var databasePath = Path.GetFullPath(Path.Combine(builder.Environment.ContentRootPath, "..", "data", "library.db"));
Directory.CreateDirectory(Path.GetDirectoryName(databasePath)!);
builder.Services.AddDbContext<LibraryDbContext>(options => options.UseSqlite($"Data Source={databasePath}"));
builder.Services.Configure<RabbitSettings>(builder.Configuration.GetSection("RabbitMQ"));
builder.Services.AddHostedService<ReservationWorker>();

await builder.Build().RunAsync();

public sealed class RabbitSettings
{
    public string Host { get; set; } = "localhost";
    public string User { get; set; } = "guest";
    public string Password { get; set; } = "guest";
}