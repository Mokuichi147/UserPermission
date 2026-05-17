---
name: release
description: Rust (PyO3/maturin) + Python プロジェクトのリリース。`pyproject.toml` のバージョン更新、Git タグ作成・push を行い、CI (GitHub Actions) がマルチプラットフォーム wheel ビルド・PyPI 公開・GitHub Release 作成を自動実行する。
---

# Release

## 概要

maturin (PyO3) ベースのプロジェクトをリリースする。
ビルド・PyPI 公開・GitHub Release 作成は CI (`release.yml`) が自動で行うため、ローカルではバージョン更新とタグ push のみ実施する。

## 前提

- リポジトリルートで作業する。
- リリース元ブランチは `main` を前提にする。現在のブランチが `main` でなければ中断して確認を取る。
- `git status --short` が空であることを必須条件にする。未コミット変更があれば中断して報告する。
- CI ワークフロー `.github/workflows/release.yml` が `v*` タグ push で起動する前提。

## 入力

- 任意: リリース対象バージョン。例: `0.4.0`
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
- ローカル main がリモートと同期していることを確認する。

### 2. バージョン更新

`pyproject.toml` の `[project].version` が対象バージョンと一致しているか確認する。

- 既に対象バージョンになっていればこのステップはスキップする。
- 異なる場合は更新してコミットする:

```bash
# pyproject.toml を編集
git add pyproject.toml
git commit -m "v{VERSION}にバージョンアップ"
git push origin main
```

### 3. タグ作成と push

```bash
git tag v{VERSION}
git push origin v{VERSION}
```

- タグ名は必ず `v{VERSION}` にする。
- タグ push により CI が自動起動し、以下を実行する:
  - Linux (x86_64, aarch64)、macOS (Intel, Apple Silicon)、Windows (x64) の wheel ビルド
  - sdist ビルド
  - PyPI 公開 (trusted publisher / OIDC)
  - GitHub Release 作成 (自動生成リリースノート + 全成果物添付)

### 4. CI 完了確認

タグ push 後、CI の状況をユーザーに報告する。

```bash
gh run list --workflow=release.yml --limit=1
```

- CI が失敗した場合は `gh run view` でログを確認し、原因を報告する。

## 完了報告

完了時は以下をまとめて報告する。

- リリースしたバージョン
- CI の起動状況
- GitHub Actions の URL（ユーザーが進捗を確認できるよう）

## 厳守事項

- ワーキングツリーが汚れている状態で進めない。
- バージョン未指定時は提案までにとどめ、確認なしで確定しない。
- ローカルでのビルド (`uv build`) や公開 (`uv publish`) は行わない。CI に任せる。
