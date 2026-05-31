"""
阶段2: 初始化项目目录架构
遵循四层架构 + 单向依赖原则

架构层级：
1. 输入层 (src/input) - 统一接收任务、类型判定、基础预处理
2. 调度层 (src/workflow) - 流程流转、状态管控、分支回退、全局调度
3. 协作层 (src/agents) - 多角色Agent交互、任务分发、协商会诊
4. 执行层 (src/code) - 代码解析、重构修改、规范校验、测试生成
5. 公共层 (src/common) - 全局共享工具（所有层级可引用）

依赖规则：
- 单向依赖：上层可引用下层，下层不可引用上层
- 依赖顺序：input -> workflow -> agents -> code
- common可被所有层级引用
- 禁止跨层级反向依赖
"""

# 当前目录结构设计如下：
"""
multi-agent-software-engineering/
├── src/
│   ├── __init__.py
│   ├── config.py              # 全局配置
│   ├── state.py               # 全局状态定义
│   │
│   ├── input/                 # 第1层：输入收敛层
│   │   ├── __init__.py
│   │   └── task_receiver.py   # 任务接收器
│   │
│   ├── workflow/              # 第2层：调度中枢层
│   │   ├── __init__.py
│   │   └── orchestrator.py    # LangGraph调度器
│   │
│   ├── agents/                # 第3层：智能协作层
│   │   ├── __init__.py
│   │   ├── base.py           # Agent基类
│   │   ├── scheduler.py       # 调度Agent
│   │   ├── developer.py       # 开发Agent
│   │   ├── architect.py       # 架构Agent
│   │   ├── reviewer.py        # 评审Agent
│   │   ├── tester.py         # 测试Agent
│   │   └── documenter.py      # 文档Agent
│   │
│   ├── code/                  # 第4层：原子执行层
│   │   ├── __init__.py
│   │   ├── parser.py          # AST解析器
│   │   ├── scanner.py         # 代码扫描器
│   │   └── formatter.py       # 代码格式化器
│   │
│   └── common/                # 公共层（所有层级可引用）
│       ├── __init__.py
│       ├── logger.py          # 日志工具
│       └── exceptions.py      # 异常定义
│
├── tests/                     # 测试目录
│   └── test_system.py
│
├── docs/                      # 文档目录
│   ├── stage1_验收报告.md
│   └── stage2_验收报告.md
│
├── scripts/                   # 脚本目录
│   ├── verify_environment.sh
│   └── verify_directory.sh
│
├── configs/                   # 配置目录
│   └── agents.yaml           # Agent配置
│
├── requirements.txt           # 核心依赖
├── requirements.lock         # 锁定版本
├── pyproject.toml           # 项目元数据
├── 计划.md                  # 100阶段计划
└── README.md                # 项目说明

依赖关系图：
┌──────────────────────────────────────┐
│              tests/                   │
│         (可测试所有层级)                │
└──────────────────────────────────────┘
                    ↑
┌──────────────────────────────────────┐
│           docs/ scripts/              │
│         (文档和工具脚本)                │
└──────────────────────────────────────┘
                    ↑
┌──────────────────────────────────────┐
│              src/                     │
│  ┌─────────────────────────────────┐  │
│  │         src/common/              │  │
│  │    (logger, exceptions, utils)   │  │
│  └─────────────────────────────────┘  │
│         ↑ 可被所有层级引用             │
│  ┌──────┴──────────────────────────┐  │
│  │         src/input/               │  │
│  │    (任务接收、类型判定、预处理)      │  │
│  └──────┬──────────────────────────┘  │
│         ↓ 可引用 common, workflow      │
│  ┌──────┴──────────────────────────┐  │
│  │         src/workflow/            │  │
│  │    (流程调度、状态管控、DAG)        │  │
│  └──────┬──────────────────────────┘  │
│         ↓ 可引用 common, agents        │
│  ┌──────┴──────────────────────────┐  │
│  │         src/agents/              │  │
│  │    (Agent协作、任务分发)           │  │
│  └──────┬──────────────────────────┘  │
│         ↓ 可引用 common, code          │
│  ┌──────┴──────────────────────────┐  │
│  │         src/code/                │  │
│  │    (代码解析、AST扫描、格式化)      │  │
│  └─────────────────────────────────┘  │
└──────────────────────────────────────┘

单向依赖规则验证：
✓ input → workflow (单向)
✓ workflow → agents (单向)
✓ agents → code (单向)
✓ common → 无外部依赖
✓ tests → src (单向)
✓ 无循环依赖
✓ 无跨层级反向依赖
"""

print(__doc__)
