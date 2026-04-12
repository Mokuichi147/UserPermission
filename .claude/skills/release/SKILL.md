---
name: release
description: uv を使う Python プロジェクトのバージョン更新、Git タグ作成、GitHub Release 作成、PyPI 公開を行う。`pyproject.toml` と `uv.lock` の更新、前回タグとの差分確認、次バージョンの提案、`dist/` 成果物の添付、対象バージョンだけの `uv publish` が必要なリリース作業で使う。
---

# Release

## 概要

uv 管理の Python プロジェクトをリリースする。
バージョンが指定されていればその値で進め、未指定であれば前回タグからの差分を確認して次バージョンを提案し、ユーザー確認を待つ。

## 前提

- リポジトリルートで作業する。
- リリース元ブランチは `main` を前提にする。現在のブランチが `main` でなければ中断して確認を取る。
- `git status --short` が空であることを必須条件にする。未コミット変更があれば中断して報告する。

## 入力

- 任意: リリース対象バージョン。例: `0.3.0`
- バージョン未指定時:
  1. 最新タグを確認する。
  2. そのタグ以降のコミットを確認する。
  3. 変更内容から妥当な SemVer 候補を 1 つ提案する。
  4. ユーザーが明示的に承認するまでファイル更新、コミット、タグ作成を進めない。

## 実行フロー

### 1. 事前確認

以下を確認する。

```bash
git status --short
git branch --show-current
git tag --sort=-v:refname | head -1
git log <LATEST_TAG>..HEAD --oneline
```

- 未コミット変更があれば中断して内容を報告する。
- 最新タグが存在しない場合は初回リリースとして扱い、履歴全体を確認対象にする。
- 差分確認では、今回のリリースに含まれる変更だけを把握する。

### 2. バージョン更新

`pyproject.toml` の `[project].version` を更新し、`uv.lock` を同期する。

```bash
uv lock
git add pyproject.toml uv.lock
git commit -m "v{VERSION}にバージョンアップ"
```

- コミット前に差分を見て、変更が `pyproject.toml` と `uv.lock` に収まっていることを確認する。
- `uv lock` に失敗した場合は原因を報告して停止する。

### 3. タグ作成とプッシュ

```bash
git tag v{VERSION}
git push origin main
git push origin v{VERSION}
```

- タグ名は必ず `v{VERSION}` にする。
- リモートへタグを送る前に `main` の push が成功していることを確認する。

### 4. ビルド

古い成果物の混在を避けるため、空の `dist/` を前提にビルドする。

```bash
uv build --clear
```

- `dist/` から今回のバージョンに対応する `.whl` と `.tar.gz` を 1 つずつ特定する。
- 配布名は `pyproject.toml` の `[project].name` を前提に判断し、別リポジトリから流用した固定名を使わない。
- ファイル名の正規化が読みにくい場合は、成果物一覧を確認して対象バージョン文字列を含むものだけを選ぶ。
- 対象候補が複数ある場合は曖昧なまま公開しない。

### 5. GitHub Release 作成

リリースノートは前回タグから今回タグまでの差分のみを日本語でまとめる。
過去バージョンの変更内容を混ぜない。

- 前回タグがある場合は `git log <LATEST_TAG>..v{VERSION} --oneline` を基準に要約する。
- 前回タグがない場合は初回リリースであることを明記し、今回含まれる変更だけを書く。
- シェルのクォート事故を避けるため、ノートは一時ファイルに書いて `--notes-file` で渡す。

```bash
gh release create v{VERSION} \
  --title "v{VERSION}" \
  --verify-tag \
  --notes-file /tmp/release-notes-v{VERSION}.md \
  dist/<WHEEL_FILE> \
  dist/<SDIST_FILE>
```

- 添付するのは今回ビルドした wheel と sdist のみとする。
- 自動生成ノートに任せず、差分に基づく日本語ノートを使う。

### 6. PyPI 公開

```bash
uv publish dist/<WHEEL_FILE> dist/<SDIST_FILE>
```

- 公開対象は今回バージョンの成果物だけに限定する。
- 認証不足や重複アップロードで失敗した場合は結果をそのまま報告する。

## 完了報告

完了時は以下をまとめて報告する。

- リリースしたバージョン
- GitHub Release URL
- 公開した成果物名
- PyPI 公開の成否

## 厳守事項

- ワーキングツリーが汚れている状態で進めない。
- バージョン未指定時は提案までにとどめ、確認なしで確定しない。
- リリースノートに過去バージョンの内容を混ぜない。
- `dist/` の古い成果物を誤って添付・公開しない。
