# Hệ thống thư viện và đặt mượn sách phân tán

Backend FastAPI sử dụng PostgreSQL để lưu sách, người dùng và yêu cầu; RabbitMQ chuyển yêu cầu `Pending` đến worker để xác nhận `Reserved` hoặc từ chối `Rejected`. Worker xử lý thông điệp có xác nhận, hàng đợi bền vững và cập nhật số bản trong cùng giao dịch cơ sở dữ liệu.

## Chạy bằng Docker Compose

Cần cài Docker Desktop và Docker Compose.

```powershell
docker compose up --build -d
docker compose exec api python -m scripts.seed
```

API: <http://localhost:8000>. Tài liệu tương tác: <http://localhost:8000/docs>.

Giao diện thư viện: <http://localhost:8000/>. Giao diện hỗ trợ đăng nhập/đăng ký, tìm kiếm theo tên sách/tác giả/số điện thoại, lọc tình trạng sách, đặt mượn, theo dõi phiếu, mượn/trả và quản lý thông tin đầu sách.

Tài khoản mẫu: `an@example.com` / `123456`.

Dữ liệu mẫu gồm người dùng `user-001` và sách `Clean Code`. Các ISBN cũ được lưu lại nội bộ khi chuyển sang trường số điện thoại.

## Chạy API cục bộ

Cần có PostgreSQL và RabbitMQ đang chạy. Tạo môi trường ảo rồi cài các gói:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL = "postgresql+psycopg://library:library@localhost:5432/library"
$env:AMQP_URL = "amqp://guest:guest@localhost:5672/%2F"
python -m scripts.seed
```

Mở hai terminal đã kích hoạt môi trường ảo:

```powershell
uvicorn app.main:app --reload
```

```powershell
python -m app.worker
```

## API

| Method | Path | Mô tả |
|---|---|---|
| `GET` | `/books?q=clean&limit=50&offset=0` | Tìm sách theo tên sách/tác giả/số điện thoại; trả số bản khả dụng |
| `GET` | `/books/{id}` | Chi tiết sách và số bản khả dụng |
| `PATCH` | `/books/{id}` | Cập nhật thông tin, số điện thoại hoặc số lượng bản sách; không cho giảm thấp hơn số bản đang giữ/đang mượn |
| `DELETE` | `/books/{id}` | Xóa sách chưa có lịch sử đặt mượn |
| `POST` | `/reservations` | Gửi yêu cầu; trả `202 Accepted` với trạng thái ban đầu `Pending` |
| `GET` | `/reservations/{id}` | Tra cứu trạng thái yêu cầu |
| `GET` | `/users/{userId}/reservations?status=Reserved` | Danh sách đặt mượn/đang mượn của người dùng |
| `POST` | `/reservations/{id}/borrow` | Chuyển yêu cầu `Reserved` thành `Borrowed` |
| `POST` | `/reservations/{id}/return` | Chuyển yêu cầu `Borrowed` thành `Returned` |
| `POST` | `/users` | Tạo người dùng |
| `POST` | `/books` | Tạo sách |
| `POST` | `/auth/register` | Đăng ký tài khoản |
| `POST` | `/auth/login` | Đăng nhập bằng email và mật khẩu |

Ví dụ tạo yêu cầu:

```json
{
  "user_id": "user-001",
  "book_id": 1
}
```

Worker chỉ giữ bản khi còn bản khả dụng; nếu hết sách, yêu cầu chuyển sang `Rejected` và có `rejection_reason`. Số bản khả dụng được tính bằng tổng số bản trừ bản đã giữ và bản đang mượn. Lỗi kết nối RabbitMQ khi gửi yêu cầu trả `503`; trạng thái yêu cầu được lưu là `Rejected` để không còn yêu cầu `Pending` bị bỏ quên.

## Kiểm thử

```powershell
pip install -r requirements.txt
pytest
```

Các endpoint tạo người dùng/sách hiện không có xác thực, phù hợp cho bài tập và môi trường demo. Trước khi triển khai thực tế, cần bổ sung xác thực và phân quyền.
