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

# サーバーとして起動する場合（uvicorn含む）
uv sync --extra server

# リレークライアントを使う場合（httpx含む）
uv sync --extra relay
```

## 使い方

### 初期化

```python
import asyncio
from user_permission import Database

async def main():
    # 初回実行時にシークレットキーを自動生成（以降はファイルから読み込み）
    async with Database("app.db", secret_key="secret.key") as db:
        # db.users / db.groups ですぐに使える
        user = await db.users.create("alice", "password123")
        group = await db.groups.create("admins")

asyncio.run(main())
```

### ユーザー管理

```python
# 作成
user = await db.users.create("alice", "password123", display_name="Alice")

# 取得
user = await db.users.get_by_id(1)
user = await db.users.get_by_username("alice")

# 一覧
users = await db.users.list_all()

# 更新（パスワード変更など）
await db.users.update(user.id, password="new_password")
await db.users.update(user.id, display_name="Alice Smith")

# 無効化
await db.users.update(user.id, is_active=False)

# 削除
await db.users.delete(user.id)
```

### 認証・トークン

```python
# ログイン認証（成功時にJWTトークンを返す、失敗時はNone）
token = await db.users.authenticate("alice", "password123")

# トークンの有効期限を指定
from datetime import timedelta
token = await db.users.authenticate("alice", "password123", expires_delta=timedelta(hours=24))

# トークン検証
payload = db.token_manager.verify_token(token)
print(payload["sub"])       # ユーザーID（文字列）
print(payload["username"])  # ユーザー名
```

### グループ管理

```python
# 作成
group = await db.groups.create("admins", description="Administrator group")

# 取得
group = await db.groups.get_by_id(1)
group = await db.groups.get_by_name("admins")

# 一覧
groups = await db.groups.list_all()

# 更新
await db.groups.update(group.id, description="Updated description")

# 削除
await db.groups.delete(group.id)
```

### グループメンバー管理

```python
# ユーザーをグループに追加
await db.groups.add_user(group.id, user.id)

# ユーザーをグループから削除
await db.groups.remove_user(group.id, user.id)

# グループのメンバー一覧
members = await db.groups.get_members(group.id)

# ユーザーの所属グループ一覧
groups = await db.groups.get_user_groups(user.id)
```

### サーバー起動

`user-permission[server]` でインストールすると、CLIからサーバーを起動できます。

```bash
uv run user-permission serve --host localhost --port 8001
```

| オプション | デフォルト | 説明 |
|---|---|---|
| `--host` | `127.0.0.1` | バインドアドレス |
| `--port` | `8000` | バインドポート |
| `--database` | `user_permission.db` | SQLiteデータベースのパス |
| `--secret` | `secret.key` | シークレットキーファイルのパス |
| `--prefix` | (なし) | APIルートプレフィックス（例: `/api`） |

### リレー（中継）

`user-permission[relay]` でインストールすると、他のアプリから中央のUserPermissionサーバーへ中継できます。
`connect()` に渡すパスを変えるだけで、ローカルDBとリレーを切り替えられます。

```python
from user_permission import connect

# ファイルパス → ローカルDB
backend = connect("app.db", secret="secret.key")

# URL → リレー（リモートサーバーへ中継）
backend = connect("http://localhost:8001")
```

#### RelayClient（プログラム的な中継）

```python
from user_permission.relay import RelayClient

async with RelayClient("http://localhost:8001") as relay:
    # ログイン
    token = await relay.login("alice", "password123")

    # トークン検証
    user = await relay.verify_token(token)

    # ユーザー・グループ操作（認証トークン付き）
    users = await relay.users.list_all(token)
    group = await relay.groups.create("admins", "Admin group", token)
    await relay.groups.add_user(group.id, user.id, token)
```

#### リレールーター（FastAPIアプリに中継ルーターをマウント）

別のFastAPIアプリにマウントすると、全リクエストが中央サーバーへ透過的に中継されます。

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from user_permission.relay import RelayClient, create_relay_router

relay = RelayClient("http://localhost:8001")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await relay.connect()
    yield
    await relay.close()

app = FastAPI(lifespan=lifespan)
app.include_router(create_relay_router(relay, prefix="/auth"))
# /auth/token, /auth/me, /auth/users, ... が全て中央サーバーへ中継される
```

### FastAPI連携

`user-permission[fastapi]` でインストールすると、ルーターを追加するだけでREST APIが使えます。

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from user_permission import Database, create_router

db = Database("app.db", secret_key="secret.key")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.close()

app = FastAPI(lifespan=lifespan)
app.include_router(create_router(db, prefix="/api"))
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

オプション（`user-permission[server]`）:
- 上記FastAPI依存に加えて:
- [uvicorn](https://pypi.org/project/uvicorn/) - ASGIサーバー

オプション（`user-permission[relay]`）:
- [httpx](https://pypi.org/project/httpx/) - 非同期HTTPクライアント

## ライセンス

MIT OR Apache-2.0
