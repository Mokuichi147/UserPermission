# UserPermission

ユーザーとグループを管理するための非同期Pythonライブラリです。

- **aiosqlite** による非同期SQLiteデータベース管理
- **pwdlib (Argon2)** によるパスワードハッシュ化
- **PyJWT** によるJWTトークンの発行・検証

## インストール

```bash
uv sync

# FastAPI連携を使う場合
uv sync --extra fastapi
```

## 使い方

### 初期化

```python
import asyncio
from user_permission import Database, TokenManager, UserManager, GroupManager

async def main():
    async with Database("app.db") as db:
        # 初回実行時にシークレットキーを自動生成（以降はファイルから読み込み）
        token_mgr = TokenManager.from_file("secret.key")
        user_mgr = UserManager(db, token_mgr)
        group_mgr = GroupManager(db, user_mgr)

asyncio.run(main())
```

### ユーザー管理

```python
# 作成
user = await user_mgr.create("alice", "password123", display_name="Alice")

# 取得
user = await user_mgr.get_by_id(1)
user = await user_mgr.get_by_username("alice")

# 一覧
users = await user_mgr.list_all()

# 更新（パスワード変更など）
await user_mgr.update(user.id, password="new_password")
await user_mgr.update(user.id, display_name="Alice Smith")

# 無効化
await user_mgr.update(user.id, is_active=False)

# 削除
await user_mgr.delete(user.id)
```

### 認証・トークン

```python
# ログイン認証（成功時にJWTトークンを返す、失敗時はNone）
token = await user_mgr.authenticate("alice", "password123")

# トークンの有効期限を指定
from datetime import timedelta
token = await user_mgr.authenticate("alice", "password123", expires_delta=timedelta(hours=24))

# トークン検証
payload = token_mgr.verify_token(token)
print(payload["sub"])       # ユーザーID（文字列）
print(payload["username"])  # ユーザー名
```

### グループ管理

```python
# 作成
group = await group_mgr.create("admins", description="Administrator group")

# 取得
group = await group_mgr.get_by_id(1)
group = await group_mgr.get_by_name("admins")

# 一覧
groups = await group_mgr.list_all()

# 更新
await group_mgr.update(group.id, description="Updated description")

# 削除
await group_mgr.delete(group.id)
```

### グループメンバー管理

```python
# ユーザーをグループに追加
await group_mgr.add_user(group.id, user.id)

# ユーザーをグループから削除
await group_mgr.remove_user(group.id, user.id)

# グループのメンバー一覧
members = await group_mgr.get_members(group.id)

# ユーザーの所属グループ一覧
groups = await group_mgr.get_user_groups(user.id)
```

### FastAPI連携

`user-permission[fastapi]` でインストールすると、ルーターを追加するだけでREST APIが使えます。

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from user_permission import (
    Database, TokenManager, UserManager, GroupManager, create_router,
)

db = Database("app.db")
token_mgr = TokenManager.from_file("secret.key")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.close()

app = FastAPI(lifespan=lifespan)

user_mgr = UserManager(db, token_mgr)
group_mgr = GroupManager(db, user_mgr)

router = create_router(db, token_mgr, user_mgr, group_mgr, prefix="/api")
app.include_router(router)
```

#### エンドポイント一覧

| メソッド | パス | 説明 | 認証 |
|---|---|---|---|
| POST | `/api/token` | ログイン（トークン取得） | 不要 |
| GET | `/api/me` | 現在のユーザー情報 | 必要 |
| POST | `/api/users` | ユーザー作成 | 不要 |
| GET | `/api/users` | ユーザー一覧 | 必要 |
| GET | `/api/users/{id}` | ユーザー取得 | 必要 |
| PATCH | `/api/users/{id}` | ユーザー更新（本人のみ） | 必要 |
| DELETE | `/api/users/{id}` | ユーザー削除（本人のみ） | 必要 |
| POST | `/api/groups` | グループ作成 | 必要 |
| GET | `/api/groups` | グループ一覧 | 必要 |
| GET | `/api/groups/{id}` | グループ取得 | 必要 |
| PATCH | `/api/groups/{id}` | グループ更新 | 必要 |
| DELETE | `/api/groups/{id}` | グループ削除 | 必要 |
| POST | `/api/groups/{id}/members` | メンバー追加 | 必要 |
| DELETE | `/api/groups/{id}/members/{user_id}` | メンバー削除 | 必要 |
| GET | `/api/groups/{id}/members` | メンバー一覧 | 必要 |
| GET | `/api/users/{id}/groups` | 所属グループ一覧 | 必要 |

## データベーススキーマ

| テーブル | 説明 |
|---|---|
| `users` | ユーザー情報（`username` は UNIQUE） |
| `groups` | グループ情報（`name` は UNIQUE） |
| `user_groups` | ユーザーとグループの多対多リレーション（複合PRIMARY KEY） |

ユーザーまたはグループを削除すると、関連する `user_groups` レコードも自動的に削除されます（CASCADE）。

## 依存パッケージ

- [aiosqlite](https://pypi.org/project/aiosqlite/) - 非同期SQLite
- [pwdlib[argon2]](https://pypi.org/project/pwdlib/) - パスワードハッシュ化
- [PyJWT](https://pypi.org/project/PyJWT/) - JWTトークン

オプション（`user-permission[fastapi]`）:
- [FastAPI](https://pypi.org/project/fastapi/) - Web APIフレームワーク
- [python-multipart](https://pypi.org/project/python-multipart/) - フォームデータ解析

## ライセンス

MIT OR Apache-2.0
