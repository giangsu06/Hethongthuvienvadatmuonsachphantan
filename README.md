# Mạch Sách

Ứng dụng thư viện gồm frontend tĩnh và backend ASP.NET Core, xử lý yêu cầu đặt mượn bất đồng bộ qua RabbitMQ. SQLite được dùng để lưu sách, bạn đọc và yêu cầu; worker và API cùng dùng `backend/data/library.db`.

## Chạy hệ thống

Cần cài Docker Desktop. Compose sẽ dựng frontend, API, worker và RabbitMQ; không cần cài .NET SDK nếu chạy toàn bộ bằng Docker.

1. Từ thư mục dự án, build và khởi động toàn bộ hệ thống:

   ```powershell
   docker compose -f backend/docker-compose.yml up --build -d
   ```

2. Mở giao diện:

   `http://localhost:5500`

   API Swagger: `http://localhost:5078/swagger`

   RabbitMQ Management: `http://localhost:15672`

   Tài khoản mặc định cho môi trường demo là `library` / `library_dev`. Có thể ghi đè bằng biến môi trường `RABBITMQ_USER` và `RABBITMQ_PASSWORD`.

3. Xem log hoặc dừng stack:

   ```powershell
   docker compose -f backend/docker-compose.yml logs -f
   docker compose -f backend/docker-compose.yml down
   ```

   Dữ liệu SQLite và RabbitMQ lưu trong Docker volumes; `down` không xóa dữ liệu. Dùng `down -v` khi muốn xóa dữ liệu demo.

Có thể chạy API/worker trực tiếp từ source để phát triển, nhưng cần .NET 10 SDK và RabbitMQ:

```powershell
docker compose -f backend/docker-compose.yml up -d rabbitmq
dotnet run --project backend/Library.Api/Library.Api.csproj --urls http://localhost:5078
dotnet run --project backend/Reservation.Worker/Reservation.Worker.csproj
py -m http.server 5500 --directory frontend
```

Trang `index.html` ở thư mục gốc cũng chuyển tới frontend này. API mặc định ở `http://localhost:5078`; có thể ghi đè bằng biến `window.MACH_SACH_API_URL` trước script frontend nếu đổi địa chỉ API.

## API

| Method | Route | Mô tả |
| --- | --- | --- |
| GET | `/books` | Danh mục và số bản khả dụng |
| GET | `/books/{id}` | Chi tiết sách |
| POST | `/reservations` | Tạo yêu cầu `Pending`, phát message vào RabbitMQ |
| GET | `/reservations/{id}` | Tra cứu trạng thái yêu cầu |
| GET | `/users/{userId}/reservations` | Danh sách yêu cầu của bạn đọc |
| PATCH | `/reservations/{id}/borrow` | Xác nhận nhận sách đã giữ |
| PATCH | `/reservations/{id}/return` | Ghi nhận trả sách và tăng số bản khả dụng |

JSON tạo yêu cầu:

```json
{
  "bookId": "BK001",
  "userId": "DG001",
  "userName": "An Nguyễn"
}
```

Trạng thái xử lý: `Pending`, `Reserved`, `Rejected`, `Borrowed`, `Returned`. RabbitMQ Management UI khả dụng tại `http://localhost:15672` với tài khoản `guest` / `guest` khi chạy cấu hình phát triển này.