use std::path::PathBuf;
use std::sync::{Arc, Mutex};

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use user_permission::Database;

use crate::error::map_core_err;
use crate::group::PyGroupManager;
use crate::token::PyTokenManager;
use crate::user::PyUserManager;

#[derive(Clone)]
pub(crate) enum DbConfig {
    Local {
        path: PathBuf,
        secret: Option<PathBuf>,
    },
    Relay {
        url: String,
    },
}

pub(crate) type SharedDb = Arc<Mutex<Option<Database>>>;

#[pyclass(module = "user_permission", name = "Database", unsendable)]
pub struct PyDatabase {
    config: DbConfig,
    pub(crate) inner: SharedDb,
}

impl PyDatabase {
    pub(crate) fn get_db(&self) -> PyResult<Database> {
        let guard = self.inner.lock().map_err(|_| {
            PyRuntimeError::new_err("internal lock poisoned")
        })?;
        guard
            .as_ref()
            .cloned()
            .ok_or_else(|| PyRuntimeError::new_err("Database is not connected. Call connect() first."))
    }
}

fn extract_path(value: &Bound<'_, PyAny>) -> PyResult<PathBuf> {
    if let Ok(s) = value.extract::<String>() {
        return Ok(PathBuf::from(s));
    }
    // pathlib.Path or os.PathLike
    let s: String = value.call_method0("__fspath__")?.extract()?;
    Ok(PathBuf::from(s))
}

#[pymethods]
impl PyDatabase {
    #[new]
    #[pyo3(signature = (backend, *, secret=None))]
    fn new(backend: &Bound<'_, PyAny>, secret: Option<&Bound<'_, PyAny>>) -> PyResult<Self> {
        let backend_str: String = if let Ok(s) = backend.extract::<String>() {
            s
        } else {
            let p = extract_path(backend)?;
            p.to_string_lossy().to_string()
        };

        let is_url = backend_str.starts_with("http://") || backend_str.starts_with("https://");
        let config = if is_url {
            if secret.is_some() {
                return Err(PyValueError::new_err(
                    "secret は HTTP バックエンドでは利用できません",
                ));
            }
            DbConfig::Relay { url: backend_str }
        } else {
            let secret_path = match secret {
                Some(s) => Some(extract_path(s)?),
                None => None,
            };
            DbConfig::Local {
                path: PathBuf::from(backend_str),
                secret: secret_path,
            }
        };

        Ok(Self {
            config,
            inner: Arc::new(Mutex::new(None)),
        })
    }

    fn connect<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let config = self.config.clone();
        let inner = self.inner.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let db = match config {
                DbConfig::Local { path, secret } => {
                    Database::open_local(path, secret).await
                }
                DbConfig::Relay { url } => Database::open_relay(&url),
            }
            .map_err(map_core_err)?;
            *inner.lock().expect("db lock poisoned") = Some(db);
            Ok(())
        })
    }

    fn close<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let db = inner.lock().expect("db lock poisoned").take();
            if let Some(db) = db {
                db.close().await.map_err(map_core_err)?;
            }
            Ok(())
        })
    }

    fn __aenter__<'py>(slf: PyRef<'py, Self>, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        let config = slf.config.clone();
        let inner = slf.inner.clone();
        let slf_obj: PyObject = slf.into_py(py);
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let db = match config {
                DbConfig::Local { path, secret } => {
                    Database::open_local(path, secret).await
                }
                DbConfig::Relay { url } => Database::open_relay(&url),
            }
            .map_err(map_core_err)?;
            *inner.lock().expect("db lock poisoned") = Some(db);
            Ok(slf_obj)
        })
    }

    #[pyo3(signature = (*_args))]
    fn __aexit__<'py>(
        &self,
        py: Python<'py>,
        _args: &Bound<'py, pyo3::types::PyTuple>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let db = inner.lock().expect("db lock poisoned").take();
            if let Some(db) = db {
                db.close().await.map_err(map_core_err)?;
            }
            Ok(())
        })
    }

    #[getter]
    fn users(&self) -> PyUserManager {
        PyUserManager::new(self.inner.clone())
    }

    #[getter]
    fn groups(&self) -> PyGroupManager {
        PyGroupManager::new(self.inner.clone())
    }

    #[getter]
    fn token_manager(&self) -> PyResult<PyTokenManager> {
        let db = self.get_db()?;
        let tm = db.token_manager().map_err(map_core_err)?.clone();
        Ok(PyTokenManager::from_inner(tm))
    }

    fn login<'py>(
        &self,
        py: Python<'py>,
        username: String,
        password: String,
    ) -> PyResult<Bound<'py, PyAny>> {
        let inner = self.inner.clone();
        pyo3_async_runtimes::tokio::future_into_py(py, async move {
            let db = inner
                .lock()
                .expect("db lock poisoned")
                .as_ref()
                .cloned()
                .ok_or_else(|| {
                    PyRuntimeError::new_err("Database is not connected. Call connect() first.")
                })?;
            db.login(&username, &password)
                .await
                .map_err(map_core_err)
        })
    }
}
