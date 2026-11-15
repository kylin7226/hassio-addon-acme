# ACME.sh SSL Certificate Manager for Home Assistant

这是一个 Home Assistant 自定义集成（custom_components），基于 [acme.sh](https://github.com/acmesh-official/acme.sh) 实现自动申请和管理 SSL 证书。

## 功能特性

- 🚀 支持多种 ACME 服务器（Let's Encrypt、ZeroSSL、Google Trust Services、Buypass、SSL.com）
- 🔒 支持 100+ 种 DNS 提供商（Cloudflare、阿里云、DNSPod、AWS Route53 等）
- 🔄 自动证书续期
- 📁 自动将证书安装到 Home Assistant SSL 目录
- 🛠️ 支持 RSA 和 ECC 证书
- 🧪 支持 Staging 环境测试
- 🎨 UI 配置界面（Config Flow）
- 📊 证书状态传感器（到期时间、剩余天数、颁发者）
- 🖼️ 支持自定义品牌图标（2026.3+）

## 安装方法

### 方法一：通过 HACS 安装（推荐）

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jyz0501&repository=hassio-addon-acme&category=integration)

1. 打开 HACS（Home Assistant Community Store）
2. 点击 **集成** → 右上角 **⋮** → **自定义仓库**
3. 添加仓库地址：`https://github.com/jyz0501/hassio-addon-acme`
4. 类别选择 **集成**
5. 点击 **添加**
6. 在 HACS 中找到 "ACME.sh SSL Certificate Manager" 并点击 **下载**
7. 重启 Home Assistant

### 方法二：手动安装

1. 下载此仓库
2. 将 `custom_components/acme_sh` 文件夹复制到您的 Home Assistant `custom_components` 目录
3. 重启 Home Assistant

## 配置

### 添加集成

1. 进入 **设置** → **设备与服务**
2. 点击右下角 **添加集成** 按钮
3. 搜索 "ACME.sh"
4. 按照配置向导填写信息：
   - **邮箱**：用于 ACME 账户注册
   - **域名**：逗号分隔的域名列表（支持通配符）
   - **DNS 提供商**：选择您的 DNS 服务商
   - **DNS 环境变量**：API 凭证（格式：`KEY1=value1;KEY2=value2`）
   - **密钥长度**：选择证书密钥类型
   - **续期天数**：到期前多少天续期
   - **测试模式**：是否使用 Staging 环境
   - **ACME 服务器**：选择证书颁发机构

### DNS 提供商配置示例

| DNS 提供商 | 代码 | 环境变量示例 |
|-----------|------|-------------|
| Cloudflare | dns_cf | `CF_Token=xxx;CF_Zone_ID=xxx` |
| 阿里云 | dns_ali | `Ali_Key=xxx;Ali_Secret=xxx` |
| DNSPod | dns_dp | `DP_Id=xxx;DP_Key=xxx` |
| GoDaddy | dns_gd | `GD_Key=xxx;GD_Secret=xxx` |
| AWS Route53 | dns_aws | `AWS_ACCESS_KEY_ID=xxx;AWS_SECRET_ACCESS_KEY=xxx` |

更多 DNS 提供商请参考 [acme.sh DNS API 文档](https://github.com/acmesh-official/acme.sh/wiki/dnsapi)

## 证书状态传感器

集成会在 `/ssl` 目录中查找域名对应的证书文件，并创建一个传感器：

- 状态：`valid` / `renewal_required` / `expired` / `not_found` / `error`
- 属性：`domain`、`domains`、`expiry_date`、`days_remaining`、`issuer`、`auto_renew`、`certificate_path`

按以下顺序查找证书（`/ssl` 与 `<配置目录>/ssl` 都会尝试）：

1. `/ssl/acme.sh/<域名>/fullchain.pem`（本 Add-on 的安装路径）
2. `/ssl/<域名>.pem`（本 Add-on 复制出的全链证书）
3. `/ssl/<域名>-fullchain.pem`
4. `/ssl/<域名>/fullchain.pem`

证书的申请与续期由 Add-on（或系统内的 acme.sh）完成，集成只负责读取并展示状态，
每 6 小时刷新一次。需要立刻触发一次申请/续期时，重启 Add-on 即可。

找不到证书时传感器显示 `not_found`，不会导致集成配置失败。

### 自动化示例

```yaml
automation:
  - alias: "SSL 证书即将到期"
    trigger:
      - platform: numeric_state
        entity_id: sensor.acme_sh_ssl_certificate
        attribute: days_remaining
        below: 15
    action:
      - service: notify.notify
        data:
          message: "SSL 证书将在 15 天内到期，请检查续期情况"
```

## Home Assistant 配置

在 `configuration.yaml` 中使用证书：

```yaml
http:
  ssl_certificate: /ssl/example.com.pem
  ssl_key: /ssl/example.com-key.pem
```

## 证书位置

Add-on 申请成功后，证书保存在：

- `/ssl/acme.sh/<domain>/cert.pem` - 证书
- `/ssl/acme.sh/<domain>/key.pem` - 私钥
- `/ssl/acme.sh/<domain>/fullchain.pem` - 完整证书链
- `/ssl/acme.sh/<domain>/ca.pem` - 中间证书

同时复制到标准位置供 Home Assistant 使用：

- `/ssl/<domain>.pem` - 完整证书链
- `/ssl/<domain>-key.pem` - 私钥

## 前置要求

集成本身只读取 `/ssl` 目录中的证书文件，不需要在 Home Assistant 配置目录里安装 acme.sh。
证书的申请与续期需要由以下任一方式完成：

### 方式一：使用 Add-on（推荐）

安装本仓库提供的 ACME.sh Add-on，它会在自己的容器内运行 acme.sh，
并把证书写入 `/ssl`。

### 方式二：手动安装

在 Home Assistant 之外的主机上安装 acme.sh，并确保证书最终落到 `/ssl`：

```bash
curl https://get.acme.sh | sh -s email=my@example.com
```

## 故障排除

### 查看日志

在 **设置** → **系统** → **日志** 中查看相关日志。

### 常见问题

1. **证书申请失败**
   - 检查 DNS 提供商的 API 密钥是否正确
   - 确认域名 DNS 解析正常
   - 检查邮箱格式是否正确

2. **传感器显示 `not_found`**
   - 确认 Add-on 已成功签发证书（查看 Add-on 日志）
   - 确认 `/ssl` 下存在与集成中填写的主域名同名的证书文件
   - 集成中填写的域名必须与 Add-on `domains` 里的第一个域名一致

3. **权限问题**
   - 确保 Home Assistant 有权限访问 SSL 目录

## 支持的 ACME 服务器

| 服务器 | 代码 | 说明 |
|-------|------|------|
| Let's Encrypt | letsencrypt | 默认，免费 |
| Let's Encrypt (Staging) | letsencrypt_test | 测试用 |
| ZeroSSL | zerossl | 免费 |
| Google Trust Services | google | 免费 |
| Buypass | buypass | 免费 |
| SSL.com | sslcom | 商业 |

## 自定义品牌图标（2026.3+）

从 Home Assistant 2026.3 版本开始，本集成支持自定义品牌图标和 Logo。

### 添加品牌图片

在集成目录的 `brand/` 文件夹中放置图片文件：

```
custom_components/acme_sh/
├── __init__.py
├── manifest.json
└── brand/
    ├── icon.png          # 集成图标（浅色主题）
    ├── dark_icon.png     # 集成图标（深色主题）
    ├── logo.png          # 集成 Logo（浅色主题）
    └── dark_logo.png     # 集成 Logo（深色主题）
```

### 支持的文件

| 文件名 | 说明 | 推荐尺寸 |
|--------|------|----------|
| `icon.png` | 集成图标（浅色） | 512x512 px |
| `icon@2x.png` | 集成图标（Retina） | 1024x1024 px |
| `dark_icon.png` | 集成图标（深色） | 512x512 px |
| `dark_icon@2x.png` | 集成图标（深色 Retina） | 1024x1024 px |
| `logo.png` | 集成 Logo（浅色） | 512x512 px |
| `logo@2x.png` | 集成 Logo（Retina） | 1024x1024 px |
| `dark_logo.png` | 集成 Logo（深色） | 512x512 px |
| `dark_logo@2x.png` | 集成 Logo（深色 Retina） | 1024x1024 px |

### 要求

- 图片必须为 PNG 格式
- 图标建议使用透明背景
- 建议同时提供浅色和深色主题变体
- 图片应为正方形

### 注意事项

- 本地品牌图片会自动优先于 brands CDN 中的图片
- 此功能需要 Home Assistant 2026.3 或更高版本
- 对于旧版本，图片将不会显示

## 许可证

MIT License

## 致谢

- [acme.sh](https://github.com/acmesh-official/acme.sh) - 强大的 ACME 协议客户端
