# LOF基金套利监控系统 - Render 部署指南

## 部署前准备：上传代码到 GitHub

### 步骤 1：在 GitHub 创建仓库
1. 打开 https://github.com 并登录
2. 点击右上角 **+** → **New repository**
3. 仓库名填写：`lof-monitor`（其他保持默认）
4. 点击 **Create repository**

### 步骤 2：上传代码
在 GitHub 仓库页面，找到 **"uploading an existing file"**，把以下文件拖进去上传：
- `app.py`
- `index.html`
- `requirements.txt`
- `render.yaml`
- `.gitignore`（如果没有，先手动创建，内容写 `__pycache__/`）

点击 **Commit changes** 完成上传。

---

## 部署到 Render

### 步骤 3：连接 GitHub
1. 打开 https://render.com 并登录（用 GitHub 账号）
2. 点击 **Dashboard** → **New** → **Blueprint**
3. 点击 **Upload a blueprint file**，上传 `render.yaml` 文件
4. 点击 **Apply Blueprint**

或者更简单的方式：
1. 打开 https://render.com 并登录
2. 点击 **Dashboard** → **New** → **Web Service**
3. 在 "Build and Deploy" 页面，选择 **Connect a GitHub repo**
4. 选择你刚才创建的 `lof-monitor` 仓库
5. 设置如下：
   - **Name**：`lof-monitor`（或任意名称）
   - **Region**：Singapore（离中国近，延迟低）
   - **Branch**：`main`
   - **Root Directory**：（留空）
   - **Runtime**：`Python`
   - **Build Command**：`pip install -r requirements.txt`
   - **Start Command**：`gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Plan**：**Free**（免费）

6. 点击 **Create Web Service**

### 步骤 4：等待部署
- Render 会自动安装依赖、启动服务
- 等待 1~3 分钟，直到状态变成 **Live**
- 部署成功后，会显示一个公开 URL，例如：
  `https://lof-monitor.onrender.com`

---

## 手机访问

部署成功后，直接在手机浏览器打开你的 URL 即可使用。

**添加到手机桌面（像 App 一样）**：
- iOS Safari：点底部分享按钮 → **添加到主屏幕**
- Android Chrome：点右上角菜单 → **添加至主屏幕**

---

## 常见问题

**Q: 部署失败怎么办？**
A: 查看 Render 控制台的 "Logs" 标签，错误信息会显示具体原因。常见问题：
- `ModuleNotFoundError` → 检查 requirements.txt 是否正确
- 超时 → Render 免费版有休眠机制，首次访问可能需要等待 30 秒唤醒

**Q: 免费版有什么限制？**
A: Render 免费版（Starter）特点：
- 每月 750 小时（够用）
- 闲置 15 分钟后会休眠，首次访问需等待 30 秒唤醒
- 不支持自定义域名（但提供免费子域名）

**Q: 如何更新代码？**
A: 更新 GitHub 仓库后，Render 会自动重新部署。

---

## 服务地址
部署成功后在这里记录你的 URL：
```
https://lof-monitor.onrender.com
```
