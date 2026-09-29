# Task 3 submission contents

The final ZIP package is organised as follows:

```text
EE5112_MiniLab1_3_Task3_Submission/
├── README.md
├── task3/
│   ├── Task3_Report.md
│   ├── README.md
│   ├── requirements-task3.txt
│   ├── action_plan.schema.json
│   ├── benchmark_cases.json
│   ├── source and automated tests
│   └── evidence/
├── task4.py
├── task2/
│   ├── EE5112_Task2_GitHub_Upload.zip
│   └── Task 2 documentation
└── video/
    └── EE5112_MiniLab1_3_Task3_Demo.mp4
```

`task3/` contains the LLM planners, local validation and direction guard, terminal chat loop,
sequential executor, Task 2 adapter, Task 4 integration, 20-command benchmark, 102 automated
tests and all written evidence. `task4.py` is included because Task 3 dispatches
`goto_object` to it. The team's Task 2 delivery is included as the platform dependency.

The MP4 is the final 1920x1080, 30 FPS, 95.8-second desktop demonstration. Its SHA-256 is:

```text
60286cd75e30b259b027c979f05546675a1a5cb6f65f1b407d9fe5bb06c28d0c
```

The package intentionally excludes API keys, `.env` files, Git metadata, Python caches,
temporary live logs, downloaded model weights and Ollama model data.
