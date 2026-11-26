let USER_ID = sessionStorage.getItem("library_user_id");
let books = [];

const $ = (selector) => document.querySelector(selector);
const grid = $("#bookGrid");

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail?.message || data.detail || "Có lỗi xảy ra");
  return data;
}

function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => element.classList.remove("show"), 2600);
}

async function loadDashboard() {
  try {
    const [dashboard, profile] = await Promise.all([
      api("/dashboard"),
      api(`/users/${USER_ID}`),
    ]);
    $("#titleCount").textContent = dashboard.title_count;
    $("#totalCopies").textContent = dashboard.total_copies;
    $("#availableCopies").textContent = dashboard.available_copies;
    $("#reservationCount").textContent = dashboard.reservation_count;
    $("#loanCount").textContent = dashboard.status_counts.Pending + dashboard.status_counts.Reserved + dashboard.status_counts.Borrowed;
    $("#profileName").textContent = profile.name;
    $("#profileEmail").textContent = profile.email;
  } catch (error) {
    toast(error.message);
  }
}

async function loadBooks() {
  grid.innerHTML = '<div class="loading"><span></span>Đang tải thư viện...</div>';
  try {
    const query = $("#searchInput").value.trim();
    const filter = $("#statusFilter").value;
    books = await api(`/books?limit=100${query ? `&q=${encodeURIComponent(query)}` : ""}`);
    if (filter === "available") books = books.filter((book) => book.available_copies > 0);
    if (filter === "unavailable") books = books.filter((book) => book.available_copies === 0);
    renderBooks();
  } catch (error) {
    grid.innerHTML = `<div class="empty-state">${error.message}</div>`;
  }
}

function renderBooks() {
  $("#resultCount").textContent = `${books.length} kết quả`;
  if (!books.length) {
    grid.innerHTML = '<div class="empty-state">Không tìm thấy đầu sách phù hợp.</div>';
    return;
  }
  grid.innerHTML = books.map((book, index) => `
    <article class="book-card">
      <div class="book-cover cover-tone-${book.id % 5}">
        <span class="book-index">BIBLIOTECH · ${String(index + 1).padStart(3, "0")}</span>
        <span class="cover-emblem">B</span>
      </div>
      <div class="book-card-heading">
        <div><h3>${escapeHtml(book.title)}</h3><span class="author">${escapeHtml(book.author)}</span></div>
        <span class="copy-status ${book.available_copies ? "" : "unavailable"}">${book.available_copies ? "Còn sách" : "Hết sách"}</span>
      </div>
      <span class="book-phone">SĐT ${book.phone_number ? escapeHtml(book.phone_number) : "chưa cập nhật"}</span>
      <div class="book-meta">
        <div><span>Có sẵn</span><strong>${book.available_copies} / ${book.total_copies} bản</strong></div>
        <div class="book-actions">
          <button class="subtle-action" data-edit-book="${book.id}" aria-label="Sửa ${escapeHtml(book.title)}" title="Sửa sách">✎</button>
          <button class="subtle-action danger" data-delete-book="${book.id}" aria-label="Xóa ${escapeHtml(book.title)}" title="Xóa sách">×</button>
          <button class="reserve-button" data-reserve="${book.id}" ${book.available_copies ? "" : "disabled"}>Đặt mượn</button>
        </div>
      </div>
    </article>
  `).join("");
}

async function loadLoans() {
  const statusFilter = $("#loanStatusFilter").value;
  const list = $("#loanList");
  list.innerHTML = '<div class="loading"><span></span>Đang tải phiếu mượn...</div>';
  try {
    const reservations = await api(`/users/${USER_ID}/reservations?limit=100${statusFilter ? `&status=${encodeURIComponent(statusFilter)}` : ""}`);
    if (!reservations.length) {
      list.innerHTML = '<div class="empty-state">Chưa có phiếu đặt mượn nào.</div>';
      return;
    }
    const booksById = new Map(books.map((book) => [book.id, book]));
    list.innerHTML = reservations.map((reservation) => {
      const book = booksById.get(reservation.book_id);
      const title = book?.title || `Sách #${reservation.book_id}`;
      const author = book?.author || "";
      const action = reservation.status === "Reserved"
        ? `<button class="loan-action" data-borrow="${reservation.id}">Mượn sách</button>`
        : reservation.status === "Borrowed"
          ? `<button class="loan-action" data-return="${reservation.id}">Trả sách</button>`
          : "";
      return `
        <article class="loan-card">
          <div class="loan-cover">${title.charAt(0).toUpperCase()}</div>
          <div class="loan-info"><strong>${escapeHtml(title)}</strong><small>${escapeHtml(author)} · ${formatDate(reservation.created_at)}</small></div>
          <span class="status-badge ${reservation.status}">${translateStatus(reservation.status)}</span>
          ${action}
        </article>
      `;
    }).join("");
  } catch (error) {
    list.innerHTML = `<div class="empty-state">${error.message}</div>`;
  }
}

function translateStatus(status) {
  return ({ Pending: "Đang xử lý", Reserved: "Đã giữ", Borrowed: "Đang mượn", Returned: "Đã trả", Rejected: "Từ chối" })[status] || status;
}

function formatDate(value) {
  return new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(value));
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[character]);
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    document.querySelectorAll(".view").forEach((view) => view.classList.remove("active"));
    const isLoans = button.dataset.view === "loans";
    $(`#${isLoans ? "loans" : "library"}View`).classList.add("active");
    $("#pageTitle").textContent = isLoans ? "Đặt mượn của tôi" : "Khám phá thư viện";
    if (isLoans) loadLoans();
  });
});

let searchTimer;
$("#searchInput").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadBooks, 250);
});
$("#statusFilter").addEventListener("change", loadBooks);
$("#loanStatusFilter").addEventListener("change", loadLoans);
$("#refreshBtn").addEventListener("click", refresh);

grid.addEventListener("click", async (event) => {
  const editButton = event.target.closest("[data-edit-book]");
  if (editButton) {
    const book = books.find((item) => item.id === Number(editButton.dataset.editBook));
    if (book) openBookModal(book);
    return;
  }
  const deleteButton = event.target.closest("[data-delete-book]");
  if (deleteButton) {
    const book = books.find((item) => item.id === Number(deleteButton.dataset.deleteBook));
    if (!book || !window.confirm(`Xóa "${book.title}" khỏi thư viện?`)) return;
    try {
      await api(`/books/${book.id}`, { method: "DELETE" });
      toast("Đã xóa đầu sách");
      await refresh();
    } catch (error) {
      toast(error.message);
    }
    return;
  }
  const button = event.target.closest("[data-reserve]");
  if (!button) return;
  button.disabled = true;
  try {
    await api("/reservations", { method: "POST", body: JSON.stringify({ user_id: USER_ID, book_id: Number(button.dataset.reserve) }) });
    toast("Đã gửi yêu cầu đặt mượn");
    await refresh();
  } catch (error) {
    toast(error.message);
    button.disabled = false;
  }
});

$("#loanList").addEventListener("click", async (event) => {
  const borrow = event.target.closest("[data-borrow]");
  const returned = event.target.closest("[data-return]");
  const id = borrow?.dataset.borrow || returned?.dataset.return;
  if (!id) return;
  try {
    await api(`/reservations/${id}/${borrow ? "borrow" : "return"}`, { method: "POST" });
    toast(borrow ? "Đã mượn sách" : "Đã trả sách");
    await refresh();
  } catch (error) {
    toast(error.message);
  }
});

const modal = $("#bookModal");
let editingBookId = null;
function openBookModal(book = null) {
  editingBookId = book?.id ?? null;
  const form = $("#bookForm");
  form.reset();
  $("#bookError").textContent = "";
  $("#bookModalTitle").textContent = book ? "Chỉnh sửa đầu sách" : "Thêm đầu sách mới";
  $("#bookSubmit").textContent = book ? "Lưu thay đổi" : "Thêm vào thư viện";
  if (book) {
    for (const field of ["title", "author", "phone_number", "total_copies"]) {
      form.elements[field].value = book[field];
    }
  }
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
}

$("#addBookBtn").addEventListener("click", () => openBookModal());
modal.addEventListener("click", (event) => {
  if (event.target.matches("[data-close], .modal-backdrop")) {
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
    editingBookId = null;
  }
});
$("#bookForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const payload = Object.fromEntries(new FormData(form));
  payload.total_copies = Number(payload.total_copies);
  $("#bookError").textContent = "";
  try {
    await api(editingBookId ? `/books/${editingBookId}` : "/books", {
      method: editingBookId ? "PATCH" : "POST",
      body: JSON.stringify(payload),
    });
    form.reset();
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
    toast(editingBookId ? "Đã cập nhật đầu sách" : "Đã thêm đầu sách mới");
    editingBookId = null;
    await refresh();
  } catch (error) {
    $("#bookError").textContent = error.message;
  }
});

async function refresh() {
  await Promise.all([loadDashboard(), loadBooks()]);
  if ($("#loansView").classList.contains("active")) await loadLoans();
}

document.querySelectorAll("[data-auth-tab]").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll("[data-auth-tab]").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".auth-form").forEach((form) => form.classList.remove("active"));
    tab.classList.add("active");
    $(`#${tab.dataset.authTab}Form`).classList.add("active");
  });
});

function enterApp(user) {
  USER_ID = user.id;
  sessionStorage.setItem("library_user_id", user.id);
  sessionStorage.setItem("library_user_name", user.name);
  sessionStorage.setItem("library_user_email", user.email);
  $("#authScreen").classList.add("hidden");
  $("#appShell").classList.add("authenticated");
  refresh();
}

$("#loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.currentTarget));
  $("#loginError").textContent = "";
  try {
    const user = await api("/auth/login", { method: "POST", body: JSON.stringify(payload) });
    enterApp(user);
  } catch (error) {
    $("#loginError").textContent = error.message;
  }
});

$("#registerForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.currentTarget));
  $("#registerError").textContent = "";
  try {
    const user = await api("/auth/register", { method: "POST", body: JSON.stringify(payload) });
    enterApp(user);
  } catch (error) {
    $("#registerError").textContent = error.message;
  }
});

$("#logoutBtn").addEventListener("click", () => {
  sessionStorage.removeItem("library_user_id");
  sessionStorage.removeItem("library_user_name");
  sessionStorage.removeItem("library_user_email");
  USER_ID = null;
  $("#appShell").classList.remove("authenticated");
  $("#authScreen").classList.remove("hidden");
});

if (USER_ID) {
  api(`/users/${USER_ID}`)
    .then(enterApp)
    .catch(() => {
      sessionStorage.removeItem("library_user_id");
      $("#authScreen").classList.remove("hidden");
    });
} else {
  $("#authScreen").classList.remove("hidden");
}
