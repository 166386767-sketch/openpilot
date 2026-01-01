<div align="center" style="text-align: center;">

<h1>China 智驾系统</h1>

<p>
  <b>为长安欧尚 Z6 iDD 深度定制的驾驶辅助系统</b>
  <br>
  基于 openpilot（MIT License）构建，开箱即用，上车自动识别车型。
</p>

<h3>
  <a href="https://chinaleads.github.io">官网 / 安装教程</a> ·
  <a href="#-安装">安装地址</a> ·
  <a href="#-功能特性">功能特性</a> ·
  <a href="#-常见问题">常见问题</a> ·
  <a href="#-许可">许可</a>
</h3>

</div>

---

## 📲 安装

在 comma 设备的 **Settings → Software → Custom Software** 中输入：

```
installer.comma.ai/ChinaLeads/openpilot
```

- 无需添加分支后缀，默认即为 Z6 iDD 适配版
- 无需手动选择车型，开机自动锁定 `CHANGAN_Z6_IDD`
- 首次安装约需下载 1.8GB 源码，请保持网络稳定

> 详细图文教程见官网：**https://chinaleads.github.io**

## 🚗 适配车型

**长安欧尚 Z6 iDD**（插电混动）

| 项目 | 说明 |
|---|---|
| 车型指纹 | `CHANGAN_Z6_IDD`（`launch_env.sh` 固定，跳过识别流程） |
| 安全模型 | `changan`（`SAFETY_CHANGAN`，含 CRC 校验与滚动计数器） |
| 横向控制 | 角度控制（直接写入 EPS 转角指令） |
| 纵向控制 | openpilot 全速域纵向控制，支持 Stop-and-Go |
| 整备质量 | 1760 kg（+136 kg 标准载荷） |
| 轴距 / 转向比 | 2.795 m / 14.5 |
| 盲区监测 | 启用（数据来自原车 BSM） |
| 驾驶员监控 | 自动关闭（本车型无内置 DMS 摄像头） |

同时保留 `CHANGAN_Z6`（燃油版）指纹定义，便于后续扩展。

## ✨ 功能特性

- **自动车型识别**：固定指纹 + 完整 changan 车型端口，上电即用
- **L2 级辅助驾驶**：车道居中 + 全速域 ACC + 自动跟停起步
- **panda 安全模型**：所有发送帧逐帧校验（CRC-8/J1850 + 4-bit 滚动计数），超差即阻断
- **China 界面**：开机向导 / 设置 / 提示 / 12 种语言翻译全面 China 化
- **自动同步上游**：CI 工作流自动合并官方 openpilot 更新，合并后自动校验 Z6 iDD 适配完整性，校验通过才发布

## ❓ 常见问题

**Q：安装地址输入后没反应？**
确认拼写区分大小写：`ChinaLeads/openpilot`；确认设备已联网。

**Q：怎么确认装的是 China 版？**
`设置 → 设备 → 关于`，版本信息显示 **China**；车型指纹应为 `CHANGAN_Z6_IDD`。

**Q：官方 openpilot 更新后会失效吗？**
不会。同步工作流在每次合并后校验车型适配（指纹、安全模型、平台注册等） ，自动合并校验人推送中止直接发布。
**Q：首次上路注意什么？**
横纵向参数为保守出厂值，请在空旷路段低速验证转向与加减速响应，异常时立即接管。

更多问题见 [官网 FAQ](https://chinaleads.github.io#faq)。

## 📁 仓库结构

| 路径 | 内容 |
|---|---|
| `openpilot/` | 主系统（selfdrive / system / tools） |
| `opendbc_repo` | 车型适配子模块 → [ChinaLeads/opendbc](https://github.com/ChinaLeads/opendbc)（`opendbc/car/changan/` + `opendbc/safety/modes/changan.h`） |
| `panda` | CAN 通信固件（上游 commaai/panda，编译时自动引入 changan 安全模型） |

## 📜 许可

本项目基于 [openpilot](https://github.com/commaai/openpilot)（MIT License）构建，保留上游原始版权声明与许可文本。
本项目定制部分（长安欧尚 Z6 iDD 车型适配、China 品牌标识）版权归本仓库所有。

**免责声明**：驾驶辅助系统不能替代驾驶员，使用时请始终保持注意力集中、手握方向盘。本系统按"现状"提供，使用风险由用户自行承担。
