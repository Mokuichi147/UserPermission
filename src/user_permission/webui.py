from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import DictLoader, Environment, select_autoescape

from .database import Database
from .user import User

COOKIE_NAME = "up_token"


_BASE = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{% block title %}UserPermission{% endblock %}</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
</head>
<body class="bg-slate-50 min-h-screen text-slate-800">
<header class="bg-white border-b">
  <div class="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
    <a href="{{ prefix }}/" class="text-lg font-semibold">UserPermission</a>
    {% if user %}
    <nav class="flex gap-4 text-sm items-center">
      <a href="{{ prefix }}/users" class="hover:underline">ユーザー</a>
      <a href="{{ prefix }}/groups" class="hover:underline">グループ</a>
      <a href="{{ prefix }}/me" class="hover:underline">プロフィール</a>
      <span class="text-slate-500">{{ user.display_name or user.username }}</span>
      {% if is_admin %}<span class="inline-block bg-amber-100 text-amber-800 text-xs px-2 py-0.5 rounded">管理者</span>{% endif %}
      <a href="{{ prefix }}/logout" class="text-red-600 hover:underline">ログアウト</a>
    </nav>
    {% else %}
    <nav class="flex gap-4 text-sm">
      <a href="{{ prefix }}/login" class="hover:underline">ログイン</a>
      <a href="{{ prefix }}/register" class="hover:underline">登録</a>
    </nav>
    {% endif %}
  </div>
</header>
<main class="max-w-5xl mx-auto p-4">
{% block content %}{% endblock %}
</main>
</body>
</html>
"""

_LOGIN = """{% extends "base.html" %}
{% block title %}ログイン{% endblock %}
{% block content %}
<div class="max-w-sm mx-auto bg-white p-6 rounded shadow mt-8">
  <h1 class="text-xl font-semibold mb-4">ログイン</h1>
  {% if error %}<p class="text-red-600 text-sm mb-3">{{ error }}</p>{% endif %}
  <form method="post" action="{{ prefix }}/login" class="space-y-3">
    <label class="block">
      <span class="text-sm">ユーザー名</span>
      <input name="username" required class="w-full border rounded px-2 py-1">
    </label>
    <label class="block">
      <span class="text-sm">パスワード</span>
      <input name="password" type="password" required class="w-full border rounded px-2 py-1">
    </label>
    <button class="w-full bg-blue-600 text-white py-1.5 rounded hover:bg-blue-700">ログイン</button>
  </form>
  <p class="text-sm mt-4 text-center">
    アカウントがない場合は<a href="{{ prefix }}/register" class="text-blue-600">登録</a>
  </p>
</div>
{% endblock %}
"""

_REGISTER = """{% extends "base.html" %}
{% block title %}登録{% endblock %}
{% block content %}
<div class="max-w-sm mx-auto bg-white p-6 rounded shadow mt-8">
  <h1 class="text-xl font-semibold mb-4">アカウント登録</h1>
  {% if error %}<p class="text-red-600 text-sm mb-3">{{ error }}</p>{% endif %}
  <form method="post" action="{{ prefix }}/register" class="space-y-3">
    <label class="block">
      <span class="text-sm">ユーザー名</span>
      <input name="username" value="{{ values.username or '' }}" required class="w-full border rounded px-2 py-1">
    </label>
    <label class="block">
      <span class="text-sm">表示名</span>
      <input name="display_name" value="{{ values.display_name or '' }}" class="w-full border rounded px-2 py-1">
    </label>
    <label class="block">
      <span class="text-sm">パスワード</span>
      <input name="password" type="password" required class="w-full border rounded px-2 py-1">
    </label>
    <button class="w-full bg-blue-600 text-white py-1.5 rounded hover:bg-blue-700">登録</button>
  </form>
  <p class="text-sm mt-4 text-center">
    既にアカウントがある場合は<a href="{{ prefix }}/login" class="text-blue-600">ログイン</a>
  </p>
</div>
{% endblock %}
"""

_INDEX = """{% extends "base.html" %}
{% block title %}ダッシュボード{% endblock %}
{% block content %}
<div class="bg-white p-6 rounded shadow">
  <h1 class="text-2xl font-semibold mb-2">こんにちは、{{ user.display_name or user.username }}さん</h1>
  <p class="text-slate-600">UserPermission 管理画面へようこそ。</p>
  <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
    <a href="{{ prefix }}/users" class="block p-4 bg-blue-50 rounded hover:bg-blue-100">
      <div class="text-sm text-slate-500">ユーザー数</div>
      <div class="text-2xl font-semibold">{{ user_count }}</div>
    </a>
    <a href="{{ prefix }}/groups" class="block p-4 bg-green-50 rounded hover:bg-green-100">
      <div class="text-sm text-slate-500">グループ数</div>
      <div class="text-2xl font-semibold">{{ group_count }}</div>
    </a>
    <a href="{{ prefix }}/me" class="block p-4 bg-amber-50 rounded hover:bg-amber-100">
      <div class="text-sm text-slate-500">プロフィール</div>
      <div class="text-lg font-medium">編集 / パスワード変更</div>
    </a>
  </div>
  {% if my_groups %}
  <div class="mt-6">
    <h2 class="font-semibold mb-2">所属グループ</h2>
    <ul class="flex flex-wrap gap-2">
      {% for g in my_groups %}
      <li><a href="{{ prefix }}/groups/{{ g.id }}" class="inline-block bg-slate-100 px-3 py-1 rounded text-sm hover:bg-slate-200">{{ g.name }}</a></li>
      {% endfor %}
    </ul>
  </div>
  {% endif %}
</div>
{% endblock %}
"""

_USERS = """{% extends "base.html" %}
{% block title %}ユーザー{% endblock %}
{% block content %}
<div class="space-y-4">
  <div class="bg-white p-4 rounded shadow">
    <h2 class="font-semibold mb-3">新規ユーザー作成</h2>
    <form hx-post="{{ prefix }}/users"
          hx-target="#users-rows"
          hx-swap="beforeend"
          hx-on::after-request="if(event.detail.successful){this.reset();document.getElementById('user-create-error').textContent='';}else{document.getElementById('user-create-error').textContent=event.detail.xhr.responseText||'作成に失敗しました';}"
          class="flex flex-wrap gap-2">
      <input name="username" placeholder="ユーザー名" required class="border rounded px-2 py-1">
      <input name="display_name" placeholder="表示名" class="border rounded px-2 py-1">
      <input name="password" type="password" placeholder="パスワード" required class="border rounded px-2 py-1">
      <button class="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">作成</button>
    </form>
    <div id="user-create-error" class="text-red-600 text-sm mt-2"></div>
  </div>

  <div class="bg-white rounded shadow overflow-hidden">
    <table class="w-full text-sm">
      <thead class="bg-slate-100 text-left">
        <tr>
          <th class="px-3 py-2">ID</th>
          <th class="px-3 py-2">ユーザー名</th>
          <th class="px-3 py-2">表示名</th>
          <th class="px-3 py-2">状態</th>
          <th class="px-3 py-2">作成日</th>
          <th class="px-3 py-2 text-right">操作</th>
        </tr>
      </thead>
      <tbody id="users-rows">
        {% for u in users %}{% include "_user_row.html" %}{% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
"""

_USER_ROW = """<tr id="user-row-{{ u.id }}" class="border-t">
  <td class="px-3 py-2">{{ u.id }}</td>
  <td class="px-3 py-2 font-mono">
    {{ u.username }}
    {% if u.is_admin %}<span class="ml-1 bg-amber-100 text-amber-800 text-xs px-1.5 py-0.5 rounded">管理者</span>{% endif %}
  </td>
  <td class="px-3 py-2">{{ u.display_name }}</td>
  <td class="px-3 py-2">
    {% if is_admin or u.id == current_user.id %}
    <button class="{% if u.is_active %}text-green-600{% else %}text-slate-400{% endif %} hover:underline"
      hx-post="{{ prefix }}/users/{{ u.id }}/active"
      hx-target="#user-row-{{ u.id }}"
      hx-swap="outerHTML">{% if u.is_active %}有効{% else %}無効{% endif %}</button>
    {% else %}
    {% if u.is_active %}<span class="text-green-600">有効</span>{% else %}<span class="text-slate-400">無効</span>{% endif %}
    {% endif %}
  </td>
  <td class="px-3 py-2 text-slate-500">{{ u.created_at }}</td>
  <td class="px-3 py-2 text-right whitespace-nowrap">
    {% if u.id == current_user.id %}
    <a href="{{ prefix }}/me" class="text-blue-600 hover:underline">編集</a>
    {% elif is_admin %}
    <a href="{{ prefix }}/users/{{ u.id }}" class="text-blue-600 hover:underline">編集</a>
    {% endif %}
    {% if is_admin and u.id != current_user.id %}
    <button class="text-amber-700 hover:underline ml-2"
      hx-post="{{ prefix }}/users/{{ u.id }}/admin"
      hx-target="#user-row-{{ u.id }}"
      hx-swap="outerHTML"
      hx-confirm="{% if u.is_admin %}{{ u.username }} を管理者から降格しますか？{% else %}{{ u.username }} を管理者に昇格しますか？{% endif %}">{% if u.is_admin %}降格{% else %}昇格{% endif %}</button>
    {% endif %}
    {% if is_admin or u.id == current_user.id %}
    <button class="text-red-600 hover:underline ml-2"
      hx-delete="{{ prefix }}/users/{{ u.id }}"
      hx-target="#user-row-{{ u.id }}"
      hx-swap="outerHTML"
      hx-confirm="{% if u.id == current_user.id %}自分のアカウントを削除しますか？{% else %}{{ u.username }} を削除しますか？{% endif %}">削除</button>
    {% endif %}
  </td>
</tr>
"""

_ME = """{% extends "base.html" %}
{% block title %}プロフィール{% endblock %}
{% block content %}
<div class="max-w-md mx-auto space-y-6">
  <div class="bg-white p-6 rounded shadow">
    <h2 class="font-semibold mb-4">プロフィール編集</h2>
    {% if profile_success %}<p class="text-green-700 text-sm mb-3">プロフィールを更新しました</p>{% endif %}
    {% if profile_error %}<p class="text-red-600 text-sm mb-3">{{ profile_error }}</p>{% endif %}
    <form method="post" action="{{ prefix }}/me" class="space-y-3">
      <label class="block">
        <span class="text-sm">ユーザー名</span>
        <input name="username" value="{{ user.username }}" required class="w-full border rounded px-2 py-1">
      </label>
      <label class="block">
        <span class="text-sm">表示名</span>
        <input name="display_name" value="{{ user.display_name }}" class="w-full border rounded px-2 py-1">
      </label>
      <button class="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">更新</button>
    </form>
  </div>

  <div class="bg-white p-6 rounded shadow">
    <h2 class="font-semibold mb-4">パスワード変更</h2>
    {% if password_success %}<p class="text-green-700 text-sm mb-3">パスワードを変更しました</p>{% endif %}
    {% if password_error %}<p class="text-red-600 text-sm mb-3">{{ password_error }}</p>{% endif %}
    <form method="post" action="{{ prefix }}/me/password" class="space-y-3">
      <label class="block">
        <span class="text-sm">現在のパスワード</span>
        <input name="current_password" type="password" required class="w-full border rounded px-2 py-1">
      </label>
      <label class="block">
        <span class="text-sm">新しいパスワード</span>
        <input name="new_password" type="password" required class="w-full border rounded px-2 py-1">
      </label>
      <button class="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">変更</button>
    </form>
  </div>

  <div class="bg-white p-6 rounded shadow">
    <h2 class="font-semibold mb-3">所属グループ</h2>
    {% if my_groups %}
    <ul class="flex flex-wrap gap-2">
      {% for g in my_groups %}
      <li><a href="{{ prefix }}/groups/{{ g.id }}" class="inline-block bg-slate-100 px-3 py-1 rounded text-sm hover:bg-slate-200">{{ g.name }}</a></li>
      {% endfor %}
    </ul>
    {% else %}
    <p class="text-sm text-slate-500">所属しているグループはありません。</p>
    {% endif %}
  </div>
</div>
{% endblock %}
"""

_GROUPS = """{% extends "base.html" %}
{% block title %}グループ{% endblock %}
{% block content %}
<div class="space-y-4">
  {% if is_admin %}
  <div class="bg-white p-4 rounded shadow">
    <h2 class="font-semibold mb-3">新規グループ作成</h2>
    <form hx-post="{{ prefix }}/groups"
          hx-target="#groups-rows"
          hx-swap="beforeend"
          hx-on::after-request="if(event.detail.successful){this.reset();document.getElementById('group-create-error').textContent='';}else{document.getElementById('group-create-error').textContent=event.detail.xhr.responseText||'作成に失敗しました';}"
          class="flex flex-wrap gap-2 items-center">
      <input name="name" placeholder="グループ名" required class="border rounded px-2 py-1">
      <input name="description" placeholder="説明" class="border rounded px-2 py-1 flex-1 min-w-0">
      <label class="text-sm flex items-center gap-1">
        <input name="is_admin" type="checkbox" value="1">
        管理者グループ
      </label>
      <button class="bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700">作成</button>
    </form>
    <div id="group-create-error" class="text-red-600 text-sm mt-2"></div>
  </div>
  {% else %}
  <p class="text-sm text-slate-500">グループの作成・削除は管理者のみ可能です。</p>
  {% endif %}

  <div class="bg-white rounded shadow overflow-hidden">
    <table class="w-full text-sm">
      <thead class="bg-slate-100 text-left">
        <tr>
          <th class="px-3 py-2">ID</th>
          <th class="px-3 py-2">名前</th>
          <th class="px-3 py-2">説明</th>
          <th class="px-3 py-2 text-right">操作</th>
        </tr>
      </thead>
      <tbody id="groups-rows">
        {% for g in groups %}{% include "_group_row.html" %}{% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
"""

_GROUP_ROW = """<tr id="group-row-{{ g.id }}" class="border-t">
  <td class="px-3 py-2">{{ g.id }}</td>
  <td class="px-3 py-2 font-semibold">
    <a href="{{ prefix }}/groups/{{ g.id }}" class="text-blue-700 hover:underline">{{ g.name }}</a>
    {% if g.is_admin %}<span class="ml-1 bg-amber-100 text-amber-800 text-xs px-1.5 py-0.5 rounded">🔑 管理者</span>{% endif %}
  </td>
  <td class="px-3 py-2 text-slate-600">{{ g.description }}</td>
  <td class="px-3 py-2 text-right whitespace-nowrap">
    <a href="{{ prefix }}/groups/{{ g.id }}" class="text-blue-600 hover:underline">詳細</a>
    {% if is_admin %}
    <button class="text-red-600 hover:underline ml-2"
      hx-delete="{{ prefix }}/groups/{{ g.id }}"
      hx-target="#group-row-{{ g.id }}"
      hx-swap="outerHTML"
      hx-confirm="グループ「{{ g.name }}」を削除しますか？">削除</button>
    {% endif %}
  </td>
</tr>
"""

_GROUP_DETAIL = """{% extends "base.html" %}
{% block title %}{{ group.name }}{% endblock %}
{% block content %}
<div class="space-y-4">
  <a href="{{ prefix }}/groups" class="text-sm text-blue-600 hover:underline">← グループ一覧</a>

  <div class="bg-white p-6 rounded shadow">
    <h2 class="font-semibold mb-4">グループ情報 {% if group.is_admin %}<span class="bg-amber-100 text-amber-800 text-xs px-2 py-0.5 rounded">🔑 管理者</span>{% endif %}</h2>
    {% if update_success %}<p class="text-green-700 text-sm mb-3">更新しました</p>{% endif %}
    {% if update_error %}<p class="text-red-600 text-sm mb-3">{{ update_error }}</p>{% endif %}
    {% if is_admin %}
    <form method="post" action="{{ prefix }}/groups/{{ group.id }}" class="space-y-3">
      <label class="block">
        <span class="text-sm">名前</span>
        <input name="name" value="{{ group.name }}" required class="w-full border rounded px-2 py-1">
      </label>
      <label class="block">
        <span class="text-sm">説明</span>
        <input name="description" value="{{ group.description }}" class="w-full border rounded px-2 py-1">
      </label>
      <label class="flex items-center gap-2 text-sm">
        <input name="is_admin" type="checkbox" value="1" {% if group.is_admin %}checked{% endif %}>
        管理者グループにする（このグループのメンバーは UserPermission を管理できます）
      </label>
      <button class="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">更新</button>
    </form>
    {% else %}
    <dl class="text-sm space-y-1">
      <div><dt class="inline font-medium">名前:</dt> <dd class="inline">{{ group.name }}</dd></div>
      <div><dt class="inline font-medium">説明:</dt> <dd class="inline">{{ group.description }}</dd></div>
    </dl>
    <p class="text-xs text-slate-500 mt-3">編集は管理者のみ可能です。</p>
    {% endif %}
  </div>

  {% if is_admin %}
  <div class="bg-white p-6 rounded shadow">
    <h2 class="font-semibold mb-3">メンバー追加</h2>
    {% if non_members %}
    <form hx-post="{{ prefix }}/groups/{{ group.id }}/members"
          hx-target="#members-rows"
          hx-swap="beforeend"
          hx-on::after-request="if(event.detail.successful){const o=this.querySelector('option[value=\\''+new FormData(this).get('user_id')+'\\']');if(o)o.remove();this.reset();document.getElementById('member-add-error').textContent='';}else{document.getElementById('member-add-error').textContent=event.detail.xhr.responseText||'追加に失敗しました';}"
          class="flex gap-2">
      <select name="user_id" required class="border rounded px-2 py-1 flex-1">
        <option value="">ユーザーを選択...</option>
        {% for u in non_members %}
        <option value="{{ u.id }}">{{ u.display_name or u.username }} ({{ u.username }})</option>
        {% endfor %}
      </select>
      <button class="bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700">追加</button>
    </form>
    <div id="member-add-error" class="text-red-600 text-sm mt-2"></div>
    {% else %}
    <p class="text-sm text-slate-500">追加可能なユーザーはいません。</p>
    {% endif %}
  </div>
  {% endif %}

  <div class="bg-white rounded shadow overflow-hidden">
    <h2 class="font-semibold p-4 border-b">メンバー一覧</h2>
    <table class="w-full text-sm">
      <thead class="bg-slate-100 text-left">
        <tr>
          <th class="px-3 py-2">ID</th>
          <th class="px-3 py-2">ユーザー名</th>
          <th class="px-3 py-2">表示名</th>
          <th class="px-3 py-2 text-right">操作</th>
        </tr>
      </thead>
      <tbody id="members-rows">
        {% for u in members %}{% include "_member_row.html" %}{% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
"""

_USER_EDIT = """{% extends "base.html" %}
{% block title %}{{ target.username }} の編集{% endblock %}
{% block content %}
<div class="max-w-md mx-auto space-y-6">
  <a href="{{ prefix }}/users" class="text-sm text-blue-600 hover:underline">← ユーザー一覧</a>

  <div class="bg-white p-6 rounded shadow">
    <h2 class="font-semibold mb-4">
      ユーザー編集
      {% if target_is_admin %}<span class="ml-1 bg-amber-100 text-amber-800 text-xs px-2 py-0.5 rounded">管理者</span>{% endif %}
    </h2>
    {% if profile_success %}<p class="text-green-700 text-sm mb-3">更新しました</p>{% endif %}
    {% if profile_error %}<p class="text-red-600 text-sm mb-3">{{ profile_error }}</p>{% endif %}
    <form method="post" action="{{ prefix }}/users/{{ target.id }}" class="space-y-3">
      <label class="block">
        <span class="text-sm">ユーザー名</span>
        <input name="username" value="{{ target.username }}" required class="w-full border rounded px-2 py-1">
      </label>
      <label class="block">
        <span class="text-sm">表示名</span>
        <input name="display_name" value="{{ target.display_name }}" class="w-full border rounded px-2 py-1">
      </label>
      <label class="flex items-center gap-2 text-sm">
        <input name="is_active" type="checkbox" value="1" {% if target.is_active %}checked{% endif %}>
        有効
      </label>
      <button class="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">更新</button>
    </form>
  </div>

  <div class="bg-white p-6 rounded shadow">
    <h2 class="font-semibold mb-4">パスワードリセット</h2>
    {% if password_success %}<p class="text-green-700 text-sm mb-3">パスワードを変更しました</p>{% endif %}
    {% if password_error %}<p class="text-red-600 text-sm mb-3">{{ password_error }}</p>{% endif %}
    <form method="post" action="{{ prefix }}/users/{{ target.id }}/password" class="space-y-3">
      <label class="block">
        <span class="text-sm">新しいパスワード</span>
        <input name="new_password" type="password" required class="w-full border rounded px-2 py-1">
      </label>
      <button class="bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700">変更</button>
    </form>
  </div>

  <div class="bg-white p-6 rounded shadow">
    <h2 class="font-semibold mb-3">所属グループ</h2>
    {% if target_groups %}
    <ul class="flex flex-wrap gap-2">
      {% for g in target_groups %}
      <li><a href="{{ prefix }}/groups/{{ g.id }}" class="inline-block bg-slate-100 px-3 py-1 rounded text-sm hover:bg-slate-200">
        {{ g.name }}{% if g.is_admin %} 🔑{% endif %}
      </a></li>
      {% endfor %}
    </ul>
    {% else %}
    <p class="text-sm text-slate-500">所属しているグループはありません。</p>
    {% endif %}
  </div>
</div>
{% endblock %}
"""

_MEMBER_ROW = """<tr id="member-row-{{ group.id }}-{{ u.id }}" class="border-t">
  <td class="px-3 py-2">{{ u.id }}</td>
  <td class="px-3 py-2 font-mono">{{ u.username }}</td>
  <td class="px-3 py-2">{{ u.display_name }}</td>
  <td class="px-3 py-2 text-right">
    {% if is_admin %}
    <button class="text-red-600 hover:underline"
      hx-delete="{{ prefix }}/groups/{{ group.id }}/members/{{ u.id }}"
      hx-target="#member-row-{{ group.id }}-{{ u.id }}"
      hx-swap="outerHTML"
      hx-confirm="メンバーから削除しますか？">削除</button>
    {% endif %}
  </td>
</tr>
"""


_TEMPLATES: dict[str, str] = {
    "base.html": _BASE,
    "login.html": _LOGIN,
    "register.html": _REGISTER,
    "index.html": _INDEX,
    "users.html": _USERS,
    "_user_row.html": _USER_ROW,
    "me.html": _ME,
    "groups.html": _GROUPS,
    "_group_row.html": _GROUP_ROW,
    "group_detail.html": _GROUP_DETAIL,
    "user_edit.html": _USER_EDIT,
    "_member_row.html": _MEMBER_ROW,
}


def create_webui_router(
    db: Database,
    *,
    prefix: str = "/ui",
    token_expires: timedelta = timedelta(hours=24),
) -> APIRouter:
    """HTMX + Tailwind + Jinja2 の管理画面ルーターを作成する。"""
    env = Environment(
        loader=DictLoader(_TEMPLATES),
        autoescape=select_autoescape(["html"]),
    )
    env.globals["prefix"] = prefix

    def render(name: str, **ctx: Any) -> HTMLResponse:
        tmpl = env.get_template(name)
        return HTMLResponse(tmpl.render(**ctx))

    def render_str(name: str, **ctx: Any) -> str:
        return env.get_template(name).render(**ctx)

    router = APIRouter(prefix=prefix)

    async def _current_user(request: Request) -> User | None:
        token = request.cookies.get(COOKIE_NAME)
        if not token:
            return None
        try:
            payload = db.token_manager.verify_token(token)
            user = await db.users.get_by_id(int(payload["sub"]))
        except Exception:
            return None
        return user if user and user.is_active else None

    async def _current_user_with_admin(
        request: Request,
    ) -> tuple[User | None, bool]:
        user = await _current_user(request)
        if user is None:
            return None, False
        return user, await db.users.is_admin(user.id)

    def _login_redirect(request: Request) -> Response:
        if request.headers.get("HX-Request"):
            return Response(
                status_code=401,
                headers={"HX-Redirect": prefix + "/login"},
            )
        return RedirectResponse(prefix + "/login", status_code=303)

    def _set_cookie(resp: Response, token: str) -> None:
        resp.set_cookie(
            COOKIE_NAME,
            token,
            httponly=True,
            samesite="lax",
            max_age=int(token_expires.total_seconds()),
            path="/",
        )

    # --- Auth ---

    @router.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request) -> Response:
        if await _current_user(request) is not None:
            return RedirectResponse(prefix + "/", status_code=303)
        return render("login.html", user=None, is_admin=False, error=None)

    @router.post("/login")
    async def login_submit(
        username: str = Form(...),
        password: str = Form(...),
    ) -> Response:
        token = await db.users.authenticate(
            username, password, expires_delta=token_expires
        )
        if token is None:
            return render(
                "login.html",
                user=None,
                is_admin=False,
                error="ユーザー名またはパスワードが間違っています",
            )
        resp = RedirectResponse(prefix + "/", status_code=303)
        _set_cookie(resp, token)
        return resp

    @router.get("/logout")
    @router.post("/logout")
    async def logout() -> Response:
        resp = RedirectResponse(prefix + "/login", status_code=303)
        resp.delete_cookie(COOKIE_NAME, path="/")
        return resp

    @router.get("/register", response_class=HTMLResponse)
    async def register_page(request: Request) -> Response:
        if await _current_user(request) is not None:
            return RedirectResponse(prefix + "/", status_code=303)
        return render("register.html", user=None, is_admin=False, error=None, values={})

    @router.post("/register")
    async def register_submit(
        username: str = Form(...),
        password: str = Form(...),
        display_name: str = Form(""),
    ) -> Response:
        try:
            await db.users.create(username, password, display_name)
        except Exception:
            return render(
                "register.html",
                user=None,
                is_admin=False,
                error="そのユーザー名は既に使われています",
                values={"username": username, "display_name": display_name},
            )
        token = await db.users.authenticate(
            username, password, expires_delta=token_expires
        )
        resp = RedirectResponse(prefix + "/", status_code=303)
        if token is not None:
            _set_cookie(resp, token)
        return resp

    # --- Dashboard ---

    @router.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> Response:
        user, admin = await _current_user_with_admin(request)
        if user is None:
            return _login_redirect(request)
        users = await db.users.list_all()
        groups = await db.groups.list_all()
        my_groups = await db.groups.get_user_groups(user.id)
        return render(
            "index.html",
            user=user,
            is_admin=admin,
            user_count=len(users),
            group_count=len(groups),
            my_groups=my_groups,
        )

    # --- Profile ---

    @router.get("/me", response_class=HTMLResponse)
    async def me_page(request: Request) -> Response:
        user, admin = await _current_user_with_admin(request)
        if user is None:
            return _login_redirect(request)
        my_groups = await db.groups.get_user_groups(user.id)
        return render("me.html", user=user, is_admin=admin, my_groups=my_groups)

    @router.post("/me")
    async def me_update(
        request: Request,
        username: str = Form(...),
        display_name: str = Form(""),
    ) -> Response:
        user, admin = await _current_user_with_admin(request)
        if user is None:
            return _login_redirect(request)
        try:
            updated = await db.users.update(
                user.id, username=username, display_name=display_name
            )
        except Exception:
            my_groups = await db.groups.get_user_groups(user.id)
            return render(
                "me.html",
                user=user,
                is_admin=admin,
                my_groups=my_groups,
                profile_error="そのユーザー名は既に使われています",
            )
        my_groups = await db.groups.get_user_groups(user.id)
        return render(
            "me.html",
            user=updated or user,
            is_admin=admin,
            my_groups=my_groups,
            profile_success=True,
        )

    @router.post("/me/password")
    async def me_password(
        request: Request,
        current_password: str = Form(...),
        new_password: str = Form(...),
    ) -> Response:
        user, admin = await _current_user_with_admin(request)
        if user is None:
            return _login_redirect(request)
        token = await db.users.authenticate(user.username, current_password)
        my_groups = await db.groups.get_user_groups(user.id)
        if token is None:
            return render(
                "me.html",
                user=user,
                is_admin=admin,
                my_groups=my_groups,
                password_error="現在のパスワードが一致しません",
            )
        await db.users.update(user.id, password=new_password)
        return render(
            "me.html",
            user=user,
            is_admin=admin,
            my_groups=my_groups,
            password_success=True,
        )

    # --- Users ---

    async def _build_user_view(u: User) -> Any:
        """テンプレート用の User オブジェクトに is_admin 属性を付与する軽量ラッパー。"""
        setattr(u, "is_admin", await db.users.is_admin(u.id))
        return u

    @router.get("/users", response_class=HTMLResponse)
    async def users_page(request: Request) -> Response:
        user, admin = await _current_user_with_admin(request)
        if user is None:
            return _login_redirect(request)
        users = await db.users.list_all()
        for u in users:
            await _build_user_view(u)
        return render(
            "users.html",
            user=user,
            is_admin=admin,
            current_user=user,
            users=users,
        )

    @router.post("/users")
    async def users_create(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        display_name: str = Form(""),
    ) -> Response:
        current, admin = await _current_user_with_admin(request)
        if current is None:
            return _login_redirect(request)
        try:
            new_user = await db.users.create(username, password, display_name)
        except Exception:
            raise HTTPException(
                status_code=409, detail="そのユーザー名は既に使われています"
            )
        await _build_user_view(new_user)
        html = render_str(
            "_user_row.html",
            u=new_user,
            current_user=current,
            is_admin=admin,
        )
        return HTMLResponse(html, status_code=201)

    @router.delete("/users/{user_id}")
    async def users_delete(request: Request, user_id: int) -> Response:
        current, admin = await _current_user_with_admin(request)
        if current is None:
            return _login_redirect(request)
        if current.id != user_id and not admin:
            raise HTTPException(status_code=403, detail="管理者権限が必要です")
        if not await db.users.delete(user_id):
            raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
        resp = HTMLResponse("")
        if current.id == user_id:
            resp.headers["HX-Redirect"] = prefix + "/login"
            resp.delete_cookie(COOKIE_NAME, path="/")
        return resp

    @router.post("/users/{user_id}/active")
    async def users_toggle_active(request: Request, user_id: int) -> Response:
        current, admin = await _current_user_with_admin(request)
        if current is None:
            return _login_redirect(request)
        if current.id != user_id and not admin:
            raise HTTPException(status_code=403, detail="管理者権限が必要です")
        target = await db.users.get_by_id(user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
        updated = await db.users.update(user_id, is_active=not target.is_active)
        if updated is None:
            raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
        await _build_user_view(updated)
        html = render_str(
            "_user_row.html",
            u=updated,
            current_user=current,
            is_admin=admin,
        )
        return HTMLResponse(html)

    @router.post("/users/{user_id}/admin")
    async def users_toggle_admin(request: Request, user_id: int) -> Response:
        current, admin = await _current_user_with_admin(request)
        if current is None:
            return _login_redirect(request)
        if not admin:
            raise HTTPException(status_code=403, detail="管理者権限が必要です")
        if current.id == user_id:
            raise HTTPException(status_code=400, detail="自分自身の管理者状態は変更できません")
        target = await db.users.get_by_id(user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
        currently_admin = await db.users.is_admin(user_id)
        await db.users.set_admin(user_id, not currently_admin)
        await _build_user_view(target)
        html = render_str(
            "_user_row.html",
            u=target,
            current_user=current,
            is_admin=admin,
        )
        return HTMLResponse(html)

    @router.get("/users/{user_id}", response_class=HTMLResponse)
    async def users_edit_page(request: Request, user_id: int) -> Response:
        current, admin = await _current_user_with_admin(request)
        if current is None:
            return _login_redirect(request)
        if current.id == user_id:
            return RedirectResponse(prefix + "/me", status_code=303)
        if not admin:
            raise HTTPException(status_code=403, detail="管理者権限が必要です")
        target = await db.users.get_by_id(user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
        target_is_admin = await db.users.is_admin(user_id)
        target_groups = await db.groups.get_user_groups(user_id)
        return render(
            "user_edit.html",
            user=current,
            is_admin=admin,
            target=target,
            target_is_admin=target_is_admin,
            target_groups=target_groups,
        )

    @router.post("/users/{user_id}")
    async def users_edit_submit(
        request: Request,
        user_id: int,
        username: str = Form(...),
        display_name: str = Form(""),
        is_active: str | None = Form(None),
    ) -> Response:
        current, admin = await _current_user_with_admin(request)
        if current is None:
            return _login_redirect(request)
        if current.id == user_id:
            return RedirectResponse(prefix + "/me", status_code=303)
        if not admin:
            raise HTTPException(status_code=403, detail="管理者権限が必要です")
        target = await db.users.get_by_id(user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
        target_is_admin = await db.users.is_admin(user_id)
        target_groups = await db.groups.get_user_groups(user_id)
        try:
            updated = await db.users.update(
                user_id,
                username=username,
                display_name=display_name,
                is_active=is_active is not None,
            )
        except Exception:
            return render(
                "user_edit.html",
                user=current,
                is_admin=admin,
                target=target,
                target_is_admin=target_is_admin,
                target_groups=target_groups,
                profile_error="そのユーザー名は既に使われています",
            )
        return render(
            "user_edit.html",
            user=current,
            is_admin=admin,
            target=updated or target,
            target_is_admin=target_is_admin,
            target_groups=target_groups,
            profile_success=True,
        )

    @router.post("/users/{user_id}/password")
    async def users_reset_password(
        request: Request,
        user_id: int,
        new_password: str = Form(...),
    ) -> Response:
        current, admin = await _current_user_with_admin(request)
        if current is None:
            return _login_redirect(request)
        if current.id == user_id:
            return RedirectResponse(prefix + "/me", status_code=303)
        if not admin:
            raise HTTPException(status_code=403, detail="管理者権限が必要です")
        target = await db.users.get_by_id(user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
        await db.users.update(user_id, password=new_password)
        target_is_admin = await db.users.is_admin(user_id)
        target_groups = await db.groups.get_user_groups(user_id)
        return render(
            "user_edit.html",
            user=current,
            is_admin=admin,
            target=target,
            target_is_admin=target_is_admin,
            target_groups=target_groups,
            password_success=True,
        )

    # --- Groups ---

    @router.get("/groups", response_class=HTMLResponse)
    async def groups_page(request: Request) -> Response:
        user, admin = await _current_user_with_admin(request)
        if user is None:
            return _login_redirect(request)
        groups = await db.groups.list_all()
        return render("groups.html", user=user, is_admin=admin, groups=groups)

    @router.post("/groups")
    async def groups_create(
        request: Request,
        name: str = Form(...),
        description: str = Form(""),
        is_admin: str | None = Form(None),
    ) -> Response:
        current, caller_admin = await _current_user_with_admin(request)
        if current is None:
            return _login_redirect(request)
        if not caller_admin:
            raise HTTPException(status_code=403, detail="管理者権限が必要です")
        try:
            group = await db.groups.create(
                name, description, is_admin=is_admin is not None
            )
        except Exception:
            raise HTTPException(
                status_code=409, detail="そのグループ名は既に使われています"
            )
        html = render_str("_group_row.html", g=group, is_admin=caller_admin)
        return HTMLResponse(html, status_code=201)

    @router.get("/groups/{group_id}", response_class=HTMLResponse)
    async def group_detail(request: Request, group_id: int) -> Response:
        user, admin = await _current_user_with_admin(request)
        if user is None:
            return _login_redirect(request)
        group = await db.groups.get_by_id(group_id)
        if group is None:
            raise HTTPException(status_code=404, detail="グループが見つかりません")
        members = await db.groups.get_members(group_id)
        member_ids = {u.id for u in members}
        all_users = await db.users.list_all() if admin else []
        non_members = [u for u in all_users if u.id not in member_ids]
        return render(
            "group_detail.html",
            user=user,
            is_admin=admin,
            group=group,
            members=members,
            non_members=non_members,
        )

    @router.post("/groups/{group_id}")
    async def group_update(
        request: Request,
        group_id: int,
        name: str = Form(...),
        description: str = Form(""),
        is_admin: str | None = Form(None),
    ) -> Response:
        user, caller_admin = await _current_user_with_admin(request)
        if user is None:
            return _login_redirect(request)
        if not caller_admin:
            raise HTTPException(status_code=403, detail="管理者権限が必要です")
        group = await db.groups.get_by_id(group_id)
        if group is None:
            raise HTTPException(status_code=404, detail="グループが見つかりません")
        try:
            group = await db.groups.update(
                group_id,
                name=name,
                description=description,
                is_admin=is_admin is not None,
            )
        except Exception:
            members = await db.groups.get_members(group_id)
            member_ids = {u.id for u in members}
            all_users = await db.users.list_all()
            non_members = [u for u in all_users if u.id not in member_ids]
            return render(
                "group_detail.html",
                user=user,
                is_admin=caller_admin,
                group=group,
                members=members,
                non_members=non_members,
                update_error="そのグループ名は既に使われています",
            )
        members = await db.groups.get_members(group_id)
        member_ids = {u.id for u in members}
        all_users = await db.users.list_all()
        non_members = [u for u in all_users if u.id not in member_ids]
        return render(
            "group_detail.html",
            user=user,
            is_admin=caller_admin,
            group=group,
            members=members,
            non_members=non_members,
            update_success=True,
        )

    @router.delete("/groups/{group_id}")
    async def group_delete(request: Request, group_id: int) -> Response:
        current, caller_admin = await _current_user_with_admin(request)
        if current is None:
            return _login_redirect(request)
        if not caller_admin:
            raise HTTPException(status_code=403, detail="管理者権限が必要です")
        if not await db.groups.delete(group_id):
            raise HTTPException(status_code=404, detail="グループが見つかりません")
        return HTMLResponse("")

    @router.post("/groups/{group_id}/members")
    async def group_add_member(
        request: Request,
        group_id: int,
        user_id: int = Form(...),
    ) -> Response:
        current, caller_admin = await _current_user_with_admin(request)
        if current is None:
            return _login_redirect(request)
        if not caller_admin:
            raise HTTPException(status_code=403, detail="管理者権限が必要です")
        group = await db.groups.get_by_id(group_id)
        target = await db.users.get_by_id(user_id)
        if group is None or target is None:
            raise HTTPException(status_code=404, detail="対象が見つかりません")
        if not await db.groups.add_user(group_id, user_id):
            raise HTTPException(status_code=409, detail="既にメンバーです")
        html = render_str(
            "_member_row.html",
            u=target,
            group=group,
            is_admin=caller_admin,
        )
        return HTMLResponse(html, status_code=201)

    @router.delete("/groups/{group_id}/members/{user_id}")
    async def group_remove_member(
        request: Request, group_id: int, user_id: int
    ) -> Response:
        current, caller_admin = await _current_user_with_admin(request)
        if current is None:
            return _login_redirect(request)
        if not caller_admin:
            raise HTTPException(status_code=403, detail="管理者権限が必要です")
        if not await db.groups.remove_user(group_id, user_id):
            raise HTTPException(status_code=404, detail="メンバーが見つかりません")
        return HTMLResponse("")

    return router
