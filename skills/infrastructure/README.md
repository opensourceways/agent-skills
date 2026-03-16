# Infrastructure Team Skills

这个目录包含 Infrastructure 团队（技术设施建设团队）专属的 skills。

## 团队职责

Infrastructure 团队负责技术设施建设，包括：
- 基础设施搭建和维护
- DevOps 工具链建设
- CI/CD 流水线优化
- 监控和日志系统
- 容器化和云原生技术

## 目录结构建议

```
infrastructure/
├── README.md           # 本文件
├── devops/            # DevOps 相关
├── monitoring/        # 监控和告警
├── deployment/        # 部署相关
└── automation/        # 自动化工具
```

## Skills 列表

当前目录下的 skills：

<!-- 在此列出你的 skills，保持更新 -->

| 名字 | 功能 |
| --- | --- |
| Github-action-diagnose | 诊断昇腾CI github action问题 |

### Github-action-diagnose

#### 使用示例

**示例 1：通过 GitHub Actions Run URL 诊断**

```
/github-action-diagnose https://github.com/my-org/my-repo/actions/runs/12345678901
```

技能会自动：
1. 提取 `owner/repo` = `my-org/my-repo`，`run_id` = `12345678901`
2. 执行 `gh run view 12345678901 --repo my-org/my-repo --log-failed`
3. 进入 5 步诊断流程

---

**示例 2：通过 Run ID 诊断（在 repo 目录下）**

```
/github-action-diagnose 12345678901
```

技能会从当前目录推断 repo，然后执行诊断。

---

**示例 3：直接粘贴日志内容**

```
/github-action-diagnose
2024-01-15T10:23:45.123Z [error] npu-smi info: ERR99999 Device not found
2024-01-15T10:23:45.456Z [error] error code 507035
2024-01-15T10:23:46.000Z Process exited with code 1
```

---

**示例输出 A：基础设施故障**

```
# GitHub Action 故障诊断报告

## 1. 故障概览
- **任务名称**: train-resnet50
- **Run ID**: 12345678901
- **故障定性**: 硬件故障
- **判定依据**: NPU 驱动报 ERR99999，Device not found

## 2. 详细诊断
- **失败步骤**: Run steps (pytest)
- **报错原文**: `npu-smi info: ERR99999 error code 507035`
- **物理节点**: a3-runner-0023 -> Pod a3-0/runner-abc -> node-a3-12
- **根因分析**: 物理机 node-a3-12 上 NPU 设备驱动异常，设备不可用
```

---

**示例输出 B：非基础设施问题**

```
未发现环境/基础设施故障。

分析依据：调度正常（Set up job 完成）、镜像拉取成功、NPU 挂载无报错。
失败发生在业务代码层：Python Traceback 指向 tests/test_model.py:42，
AssertionError: expected accuracy > 0.8, got 0.75。
```

## 团队规范

请在此添加团队特定的规范或约定。

## 联系方式

Infrastructure Team 负责人：[添加联系方式]
