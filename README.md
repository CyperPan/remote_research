# remotelab

将 Web 终端集成到网页中，实现 **「有浏览器的地方就能控制服务器」**。结合「手机 - 树莓派（堡垒机）- 电脑（实验机）」架构，构成典型的堡垒机（Jump Server）访问模式。

## 架构概览

- **手机（客户端）**：通过浏览器访问树莓派上的 Web 终端。
- **树莓派（堡垒机）**：运行 Web 终端服务（如 ttyd），将网页中的指令经 SSH 转发到目标机。
- **电脑（目标机）**：接收来自树莓派的 SSH，执行 CrewAI、MoE 等实验任务。

```
手机浏览器 → 树莓派:端口(Web 终端) → SSH → MacBook / GPU 服务器
```

## 快速开始

1. 在树莓派上部署 Web 终端（推荐 [ttyd](https://github.com/tsl0922/ttyd)）：`ttyd -p 7681 bash`。
2. 配置树莓派到目标机的 SSH 公钥免密登录：`ssh-copy-id user@computer_ip`。
3. 手机与树莓派不在同一网络时，使用 [Tailscale](https://tailscale.com/) 组网，或使用 frp/cpolar 做端口映射。

**详细部署步骤、命令说明、外网访问方案与故障排查，请参阅 [开发指南](docs/DEVELOPMENT_GUIDE.md)。**

## 前置条件

- 树莓派（已联网，建议 24 小时在线）
- 目标机（MacBook、GPU 服务器等，支持 SSH）
- 手机或任意带浏览器的设备
- 外网访问（可选）：Tailscale 或 frp / cpolar

## 文档

- [开发指南](docs/DEVELOPMENT_GUIDE.md)：完整实现步骤、网络拓扑、安全与故障排查

## License

本仓库以文档与方案为主，可按需使用与修改。
