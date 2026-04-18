# SSH Jupyter Console

基于浏览器的 Jupyter Lab 远程管理面板，通过 SSH 连接 HPC 集群或远程服务器，在一个标签页内完成 Jupyter 启动、终端操作、文件管理和代码编辑。

## 功能

- **SSH 连接**，支持 Duo 双因子认证（keyboard-interactive）
- **Jupyter Lab 管理** — 启动/停止实例，自动端口转发，按服务器保存预设配置
- **浏览器终端** — 基于 xterm.js + WebSocket 的完整终端
- **远程文件浏览器** — 列表/网格视图，支持上传、下载、重命名、复制、移动、拖拽
- **代码编辑器** — Monaco Editor，语法高亮，主题/字体/语言可选，设置自动保存

## 环境要求

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) 或 pip

> 前端已预先构建并包含在仓库中，普通用户无需安装 Node.js。仅在需要修改前端代码时才需要 Node.js 18+。

## 安装与启动

### 1. 安装后端依赖

**使用 uv（推荐）：**
```bash
uv sync
```

**使用 pip：**
```bash
pip install -r requirements.txt
```

### 2. 配置 SSH 凭据

复制示例文件并填写你的信息：

```bash
cp ssh_config.example.json ssh_config.json
```

编辑 `ssh_config.json`：
```json
{
    "host": "your-server.example.com",
    "username": "your_username",
    "password": "your_password"
}
```

也可以通过环境变量指定（无需配置文件）：

```bash
export DASHBOARD_HOST=your-server.example.com
export DASHBOARD_USERNAME=your_username
export DASHBOARD_PASSWORD=your_password
```

### 3. 启动

**快速启动（推荐）：**
```bash
# 使用默认端口 8000
uv run launch.py

# 或指定自定义端口
uv run launch.py 8001
```

启动脚本会自动同步端口配置并启动后端。在浏览器中打开 `http://localhost:8000`（或自定义端口）即可使用。

**手动启动（替代方式）：**
```bash
# 使用 uv
uv run uvicorn main:app --host 0.0.0.0 --port 8000

# 使用 pip
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 配置文件说明

首次运行时自动创建，无需手动创建。

| 文件 | 内容 |
|------|------|
| `ssh_config.json` | SSH 主机、用户名、密码 |
| `presets_config.json` | 初始化脚本、各服务器的 Jupyter 实例预设 |
| `app_config.json` | 服务器监听地址、文件查看器设置、编辑器偏好 |

> **注意**：`ssh_config.json` 以明文存储密码，请勿提交到版本控制系统。

## 前端开发

如需修改前端代码，需要 Node.js 18+：

```bash
cd frontend
npm install
npm run build
```

构建完成后请将 `frontend/dist/` 一并提交，以便其他用户无需 Node.js 即可使用。
