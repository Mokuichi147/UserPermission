//! HTMX + Tailwind WebUI (placeholder).
//!
//! TODO: port `src/user_permission/webui.py` (12 Jinja2 templates + 20+ routes)
//! to askama. For now this exposes an empty router so `WebConfig::webui_enabled`
//! has a working shape; building the full WebUI lands in a follow-up commit.

use std::sync::Arc;

use axum::response::Html;
use axum::routing::get;
use axum::Router;

use crate::state::AppState;

pub fn router() -> Router<Arc<AppState>> {
    Router::new().route("/", get(placeholder))
}

async fn placeholder() -> Html<&'static str> {
    Html(
        "<!doctype html><meta charset=\"utf-8\"><title>UserPermission</title>\
         <body style=\"font-family:sans-serif;padding:2rem\">\
         <h1>UserPermission</h1>\
         <p>The HTMX WebUI is not yet ported to the Rust implementation. \
         Please use the REST API at <code>/token</code>, <code>/users</code>, etc.</p>\
         </body>",
    )
}
