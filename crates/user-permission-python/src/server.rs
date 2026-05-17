use std::path::PathBuf;
use std::time::Duration;

use pyo3::prelude::*;
use user_permission::{build_app, WebConfig};
use user_permission_core::Database;

use crate::error::map_core_err;

#[pyfunction]
#[pyo3(signature = (
    *,
    database = "user_permission.db".to_string(),
    secret = "secret.key".to_string(),
    host = "127.0.0.1".to_string(),
    port = 8000u16,
    prefix = "".to_string(),
    webui = false,
    webui_prefix = "/ui".to_string(),
))]
pub fn serve(
    py: Python<'_>,
    database: String,
    secret: String,
    host: String,
    port: u16,
    prefix: String,
    webui: bool,
    webui_prefix: String,
) -> PyResult<Bound<'_, PyAny>> {
    pyo3_async_runtimes::tokio::future_into_py(py, async move {
        let db = Database::open_local(PathBuf::from(&database), Some(PathBuf::from(&secret)))
            .await
            .map_err(map_core_err)?;
        let config = WebConfig {
            api_prefix: prefix,
            webui_prefix,
            webui_enabled: webui,
            token_expires: Duration::from_secs(3600),
            webui_token_expires: Duration::from_secs(86_400),
        };
        let app = build_app(db, config);
        let addr = format!("{host}:{port}");
        let listener = tokio::net::TcpListener::bind(&addr)
            .await
            .map_err(|e| pyo3::exceptions::PyOSError::new_err(e.to_string()))?;
        axum::serve(listener, app)
            .await
            .map_err(|e| pyo3::exceptions::PyOSError::new_err(e.to_string()))?;
        Ok(())
    })
}
