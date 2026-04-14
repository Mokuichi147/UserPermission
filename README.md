# UserPermission

![PyPI - License](https://img.shields.io/pypi/l/user-permission?cacheSeconds=0)
![PyPI - Version](https://img.shields.io/pypi/v/user-permission?cacheSeconds=0)
![Pepy Total Downloads](https://img.shields.io/pepy/dt/user-permission?cacheSeconds=0)

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

# Web管理画面を使う場合（FastAPI + Jinja2 + HTMX + Tailwind CSS）
uv sync --extra webui

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
    async with Database("app.db", secret="secret.key") as db:
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
| `--webui` | 無効 | Web管理画面（HTMX+Tailwind+Jinja2）を有効化 |
| `--webui-prefix` | `/ui` | 管理画面のURLプレフィックス |

```bash
# APIと管理画面を同時に起動
uv run user-permission serve --prefix /api --webui
# → API: http://localhost:8000/api/*
# → 管理画面: http://localhost:8000/ui/
```

### リレー（中継）

`user-permission[relay]` でインストールすると、`Database` に URL を渡すだけで、
ローカル SQLite と中央の UserPermission サーバーを同じインターフェースで切り替えられます。

```python
from user_permission import Database

# ファイルパス → ローカル SQLite
db = Database("app.db", secret="secret.key")

# URL → リレー（リモートサーバーへ HTTP 中継）
db = Database("http://localhost:8001")
```

どちらでも `db.users` / `db.groups` の API は共通です。

```python
async with Database("http://localhost:8001") as db:
    # ログイン
    token = await db.users.authenticate("alice", "password123")

    # トークン検証
    user = await db.verify_token(token)

    # ユーザー・グループ操作（認証トークン付き）
    users = await db.users.list_all(token)
    group = await db.groups.create("admins", "Admin group", token)
    await db.groups.add_user(group.id, user.id, token)
```

#### リレールーター（FastAPIアプリに中継ルーターをマウント）

別のFastAPIアプリにマウントすると、全リクエストが中央サーバーへ透過的に中継されます。

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from user_permission import Database, create_relay_router

db = Database("http://localhost:8001")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.close()

app = FastAPI(lifespan=lifespan)
app.include_router(create_relay_router(db, prefix="/auth"))
# /auth/token, /auth/me, /auth/users, ... が全て中央サーバーへ中継される
```

### FastAPI連携

`user-permission[fastapi]` でインストールすると、ルーターを追加するだけでREST APIが使えます。

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from user_permission import Database, create_router

db = Database("app.db", secret="secret.key")

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
| GET | `/api/me` | 現在のユーザー情報（`is_admin` を含む） | 必要 |
| POST | `/api/users` | ユーザー作成 | 不要 |
| GET | `/api/users` | ユーザー一覧 | 必要 |
| GET | `/api/users/{id}` | ユーザー取得 | 必要 |
| PATCH | `/api/users/{id}` | ユーザー更新 | 本人 or 管理者 |
| DELETE | `/api/users/{id}` | ユーザー削除 | 本人 or 管理者 |
| POST | `/api/groups` | グループ作成 | 管理者 |
| GET | `/api/groups` | グループ一覧 | 必要 |
| GET | `/api/groups/{id}` | グループ取得 | 必要 |
| PATCH | `/api/groups/{id}` | グループ更新 | 管理者 |
| DELETE | `/api/groups/{id}` | グループ削除 | 管理者 |
| POST | `/api/groups/{id}/members` | メンバー追加（管理者グループへの追加が昇格） | 管理者 |
| DELETE | `/api/groups/{id}/members/{user_id}` | メンバー削除（管理者グループから外すと降格） | 管理者 |
| GET | `/api/groups/{id}/members` | メンバー一覧 | 必要 |
| GET | `/api/users/{id}/groups` | 所属グループ一覧 | 必要 |

### 管理者ロール

UserPermission サーバー自身の管理権限（ユーザー/グループ/管理者の管理）は `groups.is_admin = 1` のグループで表現します。
このフラグが立った**管理者グループ**に所属しているユーザーが「UserPermission 管理者」です。

- 管理者は他ユーザーの編集・削除、グループの作成・更新・削除、メンバー管理が可能
- 他ユーザーの管理者昇格/降格は、管理者グループへの加入/脱退で行う
- 管理者グループは複数作れる（運用で分けたい場合）
- **消費サービス側の「アプリ管理者」などの概念はこの権限とは別**で、通常のグループ（`is_admin = 0`）で自由に表現してください

#### 初回セットアップ

最初に作成されたユーザーは**自動的に管理者グループに加入**します。`admin` という名前のグループが無ければ、`is_admin = 1` で新規作成されます。

```bash
# 新しいDBで最初のユーザーを登録するだけで管理者になる
uv run user-permission serve --database app.db --secret secret.key --webui
# ブラウザで /ui/register から alice を作成 → 自動的に管理者
```

#### 既存DBのマイグレーション

v0.2.0 以降は起動時に `groups.is_admin` 列の存在を確認し、無ければ `ALTER TABLE` で追加します。既存データは壊しません。
既存のDBには管理者がまだ存在しないため、Python から手動で昇格させます。

```python
import asyncio
from user_permission import Database

async def main():
    async with Database("app.db", secret="secret.key") as db:
        # 既存の好きなグループを管理者グループにする
        group = await db.groups.get_by_name("admins")
        await db.groups.update(group.id, is_admin=True)
        # あるいは新規に作って任意ユーザーを加える
        admin_group = await db.groups.create("admin", "管理者", is_admin=True)
        user = await db.users.get_by_username("alice")
        await db.groups.add_user(admin_group.id, user.id)

asyncio.run(main())
```

### Web管理画面

`user-permission[webui]` でインストールすると、ブラウザ上でアカウント・グループを管理できる画面が追加されます。
FastAPI + Jinja2 + HTMX + Tailwind CSS（CDN）で構成されており、`create_webui_router` をマウントするか、
CLI の `--webui` フラグで有効化できます。

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from user_permission import Database, create_router, create_webui_router

db = Database("app.db", secret="secret.key")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.close()

app = FastAPI(lifespan=lifespan)
app.include_router(create_router(db, prefix="/api"))
app.include_router(create_webui_router(db, prefix="/ui"))
# → /ui/login, /ui/register, /ui/users, /ui/groups, /ui/me ...
```

`create_app(webui=True)` を使えばAPIと管理画面を一括で有効化できます。

```python
from user_permission import create_app

app = create_app(
    database="app.db",
    secret="secret.key",
    prefix="/api",
    webui=True,
    webui_prefix="/ui",
)
```

#### 画面一覧

| パス | 説明 |
|---|---|
| `/ui/login` | ログイン |
| `/ui/register` | 新規アカウント登録（登録と同時にログイン） |
| `/ui/logout` | ログアウト（Cookieを破棄） |
| `/ui/` | ダッシュボード（ユーザー数・グループ数・所属グループ） |
| `/ui/me` | プロフィール編集 / パスワード変更 / 所属グループ |
| `/ui/users` | ユーザー一覧・作成（管理者は他ユーザーの編集・削除・有効/無効切替・管理者昇格/降格が可能） |
| `/ui/groups` | グループ一覧（作成・削除は管理者のみ） |
| `/ui/groups/{id}` | グループ編集・メンバー追加/削除（管理者のみ） |

認証はHTTPOnly Cookie（JWT）で管理され、トークンの有効期限は `create_webui_router(token_expires=...)` で調整できます（デフォルト24時間）。

管理者グループには一覧で「🔑 管理者」バッジが表示されます。管理者昇格/降格は、ユーザー一覧行のボタンから行えます（内部的には管理者グループへの加入/脱退）。

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

オプション（`user-permission[webui]`）:
- 上記FastAPI依存に加えて:
- [Jinja2](https://pypi.org/project/Jinja2/) - テンプレートエンジン（HTMX + Tailwind CSS はCDNから配信）

オプション（`user-permission[server]`）:
- 上記FastAPI・Jinja2依存に加えて:
- [uvicorn](https://pypi.org/project/uvicorn/) - ASGIサーバー

オプション（`user-permission[relay]`）:
- [httpx](https://pypi.org/project/httpx/) - 非同期HTTPクライアント

## ライセンス

MIT OR Apache-2.0
