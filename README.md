# RepoDoc

RepoDoc: Automated Documentation Generation and Maintenance via Repository Knowledge Graph

This forked version fixed some personnal issues:

- Reworked JSON management + prompting + thinking mode to better handle Qwen3.6.
- Added a progress tracker to better grasp the length of documentation generation.
- Fixed some issues with leaf node management accross the clustering phase.

## Usage

```bash
repodoc analyze <repo_path>
repodoc cluster <repo_path>
repodoc docs <repo_path>
repodoc generate <repo_path>
repodoc update <repo_path>
```

## Configuration

Create `.env`:

```
LLM_BASE_URL=<endpoint>
LLM_API_KEY=<key>
MAIN_MODEL=<model>
```
