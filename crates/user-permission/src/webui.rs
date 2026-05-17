//! HTMX + Tailwind WebUI (placeholder).
//!
//! TODO: port `src/user_permission/webui.py` (12 Jinja2 templates + 20+ routes)
//! to askama. For now this serves a single info page for every path under the
//! WebUI prefix so users land on something readable instead of a 404 — both
//! when their browser follows the root redirect to `/ui/` and when they try
//! the legacy `/ui/login`, `/ui/register`, `/ui/users`, etc.

use std::sync::Arc;

use axum::response::Html;
use axum::Router;

use crate::state::AppState;

pub fn router() -> Router<Arc<AppState>> {
    // `fallback` catches every legacy v0.3 path (`/login`, `/register`,
    // `/users`, …) so users land on the info page instead of a 404. The
    // nest root (`/ui` *with* trailing slash) is hooked separately in
    // `build_app` because axum 0.7's nest does not dispatch on it.
    Router::new().fallback(placeholder)
}

pub async fn placeholder() -> Html<&'static str> {
    Html(PLACEHOLDER_HTML)
}

const PLACEHOLDER_HTML: &str = r#"<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>UserPermission</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 min-h-screen text-slate-800">
<main class="max-w-2xl mx-auto p-8 space-y-4">
  <h1 class="text-2xl font-semibold">UserPermission</h1>
  <p class="text-slate-600">
    v0.4 では Web 管理画面 (HTMX + Tailwind) を Rust 側へ再移植中のため、まだ全画面が用意できていません。
    当面は REST API か <code>v0.3</code> をご利用ください。
  </p>
  <div class="bg-white p-4 rounded shadow text-sm space-y-2">
    <div><strong>REST API:</strong> <code>POST /token</code> / <code>GET /me</code> / <code>POST /users</code> / <code>GET /users</code> / <code>POST /groups</code> ...</div>
    <div><strong>進捗:</strong> 旧 <code>webui.py</code> のテンプレート 12 個 + ハンドラ 20+ を askama に移植予定です。</div>
  </div>
</main>
</body>
</html>"#;
