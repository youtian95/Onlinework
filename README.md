# 在线作业系统

## 为什么要做

在AI时代，大学生的作业质量甚至在下降，很多同学直接使用AI工具完成作业，导致过程和结果都不对。本来作业题目基本是书上的例题的变体，以前的学生还会照着书本一步步做题，还有不少同学全队。现在的学生直接把题目输入AI工具，得到答案就交上去了，错得离谱。

为了强制学生去自主学习和掌握知识点，决定开发一个在线作业系统，要求每个学生的题目参数随机生成，每个空可以输入的次数有限制，无法直接使用AI工具完成作业。

## 特色

### 题目创建

- 题目使用markdown格式编写
- 检查答案正误使用python脚本

### 学生端

- 能够根据每个人的学号随机生成题目参数
- 每个输入答案的位置可以个性化设置能做错几次，超过次数题目就不能提交
- 实时保存答题进度，显示分数
- 能显示得分排行

## 使用说明

### 1. 教师使用

#### 管理员页面

1. 访问 `/admin` 进入管理后台（也可以在登录页点击底部链接跳转）。
1. 默认管理员密码为 `admin123`。
    > 注意：生产环境请务必在 `.env.secret` 文件中修改 `ADMIN_PASSWORD`。
1. **导入学生名单**：
    - 准备一个 `csv` 文件，必须包含表头 `student_id` (学号), `name` (姓名), `enabled` (是否启用,填true/false)。
    - 示例内容：

        ```csv
        student_id,name,enabled
        2024001,张三,true
        2024002,李四,true
        ```

    - 在管理后台点击上传文件，只有被导入的学生才能登录系统。
  
#### 出题说明

1. **题目内容编写（problem.md）**：

    - 使用 Markdown 语法编写题目内容。
    - 使用 `{{ input('ans_1') }}` 定义填空项，`ans_1` 是该填空的唯一 ID。
    - 可以使用 `{{ a }}`, `{{ b }}` 等变量表示题目参数，这些参数将在脚本中生成。
    - 示例：

        ```markdown
        # 基础加法

        (1) 请计算下式的结果： $ {{ a }} + {{ b }} = $ {{ input("ans_1") }} 

        (2) 请计算下式的结果： $ {{ a }} - {{ b }} = $ {{ input("ans_2") }}
        ```

2. **题目逻辑编写（script.py）**：
    - Python 脚本包含三个部分：`meta`（元数据）、`generate`（参数生成）、`check`（答案校验）。
    - **`meta` 变量（必填）**：定义题目名称和每个填空的配置（最大尝试次数、分值）。
    - **`generate` 函数（必填）**：
        - 接收 `rng`（一个基于学号固定的随机数生成器）。
        - 使用 `rng.randint(min, max)` 等方法生成随机数。
        - 返回一个字典，包含 `problem.md` 中需要的变量（如 `a`, `b`）。
    - **`check` 函数（必填）**：
        - 接收 `params`（生成的参数）和 `user_answers`（学生提交的答案）。
        - 校验逻辑：验证学生填写的 `user_answers['id']` 是否等于预期结果。
        - 返回一个字典，包含每个 ID 的 `True`（正确）或 `False`（错误）状态。
    - 示例代码：

    ```python
    meta = {
        "title": "整数加法练习",
        "inputs": {
            "ans_1": {"max_attempts": 3}, # 定义 ans_1 最多尝试3次
        }
    }

    def generate(rng):
        # 必须使用传入的 rng 生成随机数，确保同一学号每次看到的数据一致
        return {
            "a": rng.randint(10, 99),
            "b": rng.randint(10, 99)
        }

    def check(params, user_answers):
        # 计算正确答案
        correct_ans = params["a"] + params["b"]
        # 获取用户输入（注意全是字符串，需要转换）
        user_val = int(user_answers.get("ans_1", 0))
        # 返回校验结果
        return {
            "ans_1": user_val == correct_ans
        }
    ```

### 2. 学生注意事项

- **把鼠标悬浮在输入框上可以看到剩余答题次数**，超过次数后该输入框将被禁用。
- **注意截止时间**，截止时间后将无法提交答案。

## 开发者文档

### 本地调试项目

- 启动前端

  ```bash
  cd frontend
  npm run dev
  ```

- 启动后端

  ```bash
  ./.env/python.exe -m uvicorn backend.main:app --reload
  ```

- 打开浏览器，访问 `http://localhost:5173`。

### 服务器部署

#### 1. 获取代码

通过 SSH 登录服务器，将代码克隆到指定目录（例如 `/opt/onlinework`）：

```bash
cd /opt
git clone https://github.com/你的用户名/你的仓库名.git onlinework
cd onlinework
```

#### 2. 配置文件

由于 `.env.secret` 包含管理员密码，默认被 Git 忽略。需要**在服务器上手动创建该文件**：

1. 在 1Panel 文件管理中进入 `/opt/onlinework`。
2. 新建文件 `.env.secret`。
3. 填入以下必需内容（请修改密钥）：

   ```ini
   # 管理员密码
   ADMIN_PASSWORD=admin123
   # JWT 签名密钥 (生产环境务必修改复杂字符串)
   SECRET_KEY=your-super-secret-key-please-change-it
   ```

#### 3. 启动服务

在项目目录下直接运行：

```bash
docker-compose up -d --build
```

#### 4. 访问

直接访问 `http://服务器IP`（默认 80 端口）即可看到系统。
前端 Nginx 已经配置好了转发规则，所有 API 请求会自动转发给后端容器。

#### 5. 后续更新

当你有新代码提交到 GitHub 后，在服务器上更新：

```bash
# 1. 拉取最新代码
git pull

# 2. 重新构建并重启 (数据不会丢失)
docker-compose up -d --build
```
