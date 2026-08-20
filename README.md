# echo-handle

基于 FastAPI 的音视频处理服务，负责接收 Arrangement 下发的同步或异步任务，并调用 `ffmpeg`、`onnxruntime`、`yt-dlp` 完成媒体处理与网络视频下载。

当前产物统一按 `mediaId` 命名，便于 Arrangement 或其他外部服务直接取用，例如：`media_xxx.mp4`、`media_xxx.m4a`、`media_xxx.instrumental.wav`，HLS 文件位于 `../Data/tasks/<mediaId>/hls/`。

异步任务在媒体处理成功后，会自动回调 Arrangement 的资源登记接口 `POST /api/tasks/{taskId}/resources`，把 HLS 与关键产物登记进 SQLite；若回调失败，Handle 会将任务标记为失败，避免出现“媒体已生成但 Arrangement 未入库”的假完成状态。

伴奏分离默认启用全局并发限流：`INSTRUMENTAL_MAX_CONCURRENCY=1`。当短时间连续提交多首媒体时，后续任务会先进入 `waiting-instrumental-slot`，拿到分离槽位后再进入 `extract-instrumental`，避免因 ONNX 并发过高导致 60% 长时间卡住。

如果 Arrangement 在异步请求里传入 `skipInstrumentalExtraction=true`，Handle 会跳过伴奏分离，但仍会生成可播放的 HLS：
- 当下载结果是“视频 + 独立音频（常见为 `m4a`）”时，使用原视频与原音频合并生成单路 HLS
- 当下载结果本身就是单个 `mp4` 时，直接生成单个 MP4 对应的 HLS

伴奏分离仍保留全局并发限流，但不再提供超时降级逻辑；一旦进入分离流程，会等待分离完成后再继续打包。

## 当前项目骨架
- `app/main.py`：FastAPI 启动入口与静态文件挂载
- `app/api/routes/tasks.py`：同步接口、异步接口与 WebSocket 状态推送
- `app/api/routes/health.py`：健康检查与运行时依赖检查
- `app/core/config.py`：环境变量与默认路径配置
- `app/models/task.py`：请求、响应与任务记录模型
- `app/services/ffmpeg_service.py`：真实 `ffmpeg` / `ffprobe` 调用与 HLS 打包
- `app/services/onnx_service.py`：Kim 分离模型封装
- `app/services/yt_dlp_service.py`：`yt-dlp` 下载封装
- `app/services/async_package_service.py`：异步下载-分离-HLS 任务编排
- `app/services/task_progress_store.py`：WebSocket 进度事件存储
- `app/services/pipeline.py`：同步业务编排入口
- `app/services/task_store.py`：SQLite 任务落盘、入口提取与公共 URL 构建
- `Dockerfile`：容器镜像构建文件
- `docker-compose.yml`：本地 Docker 编排文件
- `.env.docker`：容器环境变量模板
- `DOCKER.md`：Docker 部署说明

## 启动要求
- 如果需要让 Arrangement 或局域网其他设备访问 `/static/...` 资源，必须使用 `0.0.0.0` 监听，而不是默认的 `127.0.0.1`
- 推荐启动命令：`python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
- 也可直接使用脚本：`powershell -ExecutionPolicy Bypass -File scripts/start_handle_lan.ps1`
- 如果返回的是 `http://192.168.x.x:8000/static/...`，但只有本机 `127.0.0.1` 能访问，通常就是启动时未绑定 `0.0.0.0` 或防火墙未放行 `8000`

## Docker 化
已提供基础 Docker 交付物：
- `Dockerfile`
- `docker-compose.yml`
- `.env.docker`
- `DOCKER.md`

容器内默认路径：
- `/app/data`
- `/app/echo_data`
- `/app/models`

宿主机挂载建议见 `DOCKER.md`。
