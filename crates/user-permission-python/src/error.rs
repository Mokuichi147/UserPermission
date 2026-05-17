use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::PyErr;
use user_permission::Error;

pub fn map_core_err(err: Error) -> PyErr {
    match err {
        Error::NotFound => PyRuntimeError::new_err("not found"),
        Error::Conflict(msg) => PyValueError::new_err(format!("conflict: {msg}")),
        Error::InvalidCredentials => PyValueError::new_err("invalid credentials"),
        Error::MissingTokenManager => {
            PyRuntimeError::new_err("Database() に secret が渡されていません。")
        }
        Error::NotConnected => {
            PyRuntimeError::new_err("Database is not connected. Call connect() first.")
        }
        Error::InvalidArgument(msg) => PyValueError::new_err(msg),
        other => PyRuntimeError::new_err(other.to_string()),
    }
}
