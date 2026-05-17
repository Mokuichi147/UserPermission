use pyo3::prelude::*;

use crate::error::map_core_err;

#[pyfunction]
pub fn hash_password(password: &str) -> PyResult<String> {
    user_permission_core::password::hash(password).map_err(map_core_err)
}

#[pyfunction]
pub fn verify_password(password: &str, hashed: &str) -> bool {
    user_permission_core::password::verify(password, hashed)
}

#[pyfunction]
pub fn load_or_create_secret(path: &str) -> PyResult<String> {
    user_permission_core::load_or_create_secret(path).map_err(map_core_err)
}
