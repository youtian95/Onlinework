# 在线作业系统说明文档

在线作业系统，每个学生的题目参数随机生成，成绩与排名实时显示。

## 特色

### 题目创建

- 题目使用markdown格式编写
- 检查答案正误使用python脚本

### 学生端

- 能够根据每个人的学号随机生成题目参数
- 每个输入答案的位置可以个性化设置能做错几次，超过次数题目就不能提交
- 实时保存答题进度，显示分数
- 实时显示得分排行

## 使用说明

### 学生使用注意事项

- **把鼠标悬浮在输入框上可以看到剩余答题次数**，超过次数后该输入框将被禁用。
- **注意截止时间**，截止时间后将无法提交答案。

### 教师使用

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

##### 题目内容编写（problem.md）

- 使用 Markdown 语法编写题目内容。
- **LaTeX 公式编写注意**：公式块 `$ ... $` 的起始 `$` 后面和结束 `$` 前面通常需要保留空格，否则无法正确渲染。同时，请勿将 `{{ input(...) }}` 放在公式块 `$ ... $` 内部，应将其放在公式外部。
- 使用 `{{ input('ans_1') }}` 定义填空项，`ans_1` 是该填空的唯一 ID。
- 可以使用 `{{ a }}`, `{{ b }}` 等变量表示题目参数，这些参数将在脚本中生成。
- 示例：

   ```markdown
   # 基础加法

   (1) 请计算下式的结果： $ {{ a }} + {{ b }} = $ {{ input("ans_1") }} 

   (2) 请计算下式的结果： $ {{ a }} - {{ b }} = $ {{ input("ans_2") }}
   ```

##### 题目批改逻辑编写（script.py）

Python 脚本包含三个部分：`meta`（元数据）、`generate`（参数生成）、`Checker 类`（答案校验）。

- **`meta` 变量（必填，`inputs` 可省略）**：定义题目名称和每个填空的配置（最大尝试次数、分值）。
  - 若 `inputs` 未填写，系统默认使用空对象 `{}`。
  - 单个填空未配置 `max_attempts` 时默认 3 次；未配置 `score` 时默认 1 分。
- **`generate` 函数（必填）**：
  - 接收 `rng`（一个基于学号固定的随机数生成器）。
  - 使用 `rng.randint(min, max)` 等方法生成随机数。
  - 返回一个字典，包含 `problem.md` 中需要的变量（如 `a`, `b`）。
- **`Checker 类`（必填，必须继承 `NumericCheckTemplate`）**：
  - 必须为每个输入框写一个“同名函数”。
  - 例如 `<input id="ans_1" />` 对应 `def ans_1(self): ...`。
  - 每个函数返回 `True` 或 `False`。
  - 系统会自动执行这些同名函数（除了以 `_` 开头的函数都会被执行），并汇总成每个输入 ID 对应的 `True/False` 字典。如果某一步因为空值、格式错误、除零等原因抛出异常，系统会自动把这个输入框判为 `False`。

示例代码：

  ```python
  from backend.services.problem_check_template import NumericCheckTemplate

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

  class AddChecker(NumericCheckTemplate):
      def ans_1(self):
          correct_ans = self.params["a"] + self.params["b"]
          return self.is_int_equal("ans_1", correct_ans)
  ```

获取参数值方法：

- `self.params["a"]`：获取 `generate` 函数返回的参数值。

获取输入值方法：

- `self.parse_float(key)`：读取并解析浮点数，解析失败直接抛异常。
- `self.parse_int(key)`：读取并解析整数，解析失败直接抛异常。
- `self.text(key)`：读取文本，空值或空字符串会抛异常。
- `self.is_close(key, expected, tol=1e-2)`：按浮点容差返回 `True/False`。
- `self.is_int_equal(key, expected)`：按整数相等返回 `True/False`。
- `self.is_int_range(key, low, high)`：按整数范围返回 `True/False`。

## 开发者文档

### 本地调试项目

- 克隆代码。

  ```bash
  git clone
  ```

- 安装依赖

    ```bash
    conda create -p ./.env python=3.12 -y
    conda activate ./.env
    pip install -r backend/requirements.txt
    pip install -e ./packages/civil-toolkit
    cd frontend
    npm install
    cd .. 
    ```

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

### 本地测试docker部署

```bash
docker compose up -d --build
```

访问 `http://localhost:5050`。

### 服务器部署

#### 1. 获取代码

通过 SSH 登录服务器，将代码克隆到指定目录（例如 `/opt/onlinework`）。

```bash
cd /opt
git clone https://github.com/你的用户名/你的仓库名.git onlinework
cd onlinework
```

如果是Github私有仓库，需要在1Panel中SSH管理里面`密钥信息`创建一个新的SSH密钥对名字必须是默认的`id_ed25519`，把公钥添加到Github设置的SSH Keys里，才能直接在服务器上使用git命令克隆代码。或者也可以在本地克隆后通过FTP工具上传到服务器指定目录。

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

- 修改端口

  默认情况下，系统在 `5050` 端口运行。如果该端口被占用，可以修改 `docker-compose.yml` 中的端口映射，例如改为 `6060`：

  ```yaml
  ports:
    - "6060:80"
  ```

- 修改容器名字，如果服务器上已经有同名容器，可能会导致部署失败。

- 部署容器

  ```bash
  docker compose up -d --build
  ```

- 直接访问 `http://服务器IP:5050`已经可以看到系统，后面添加域名和 HTTPS。
- 在阿里云中添加域名解析`njtechsteel.youtian95.cn`，指向服务器 IP。
- 在1panel中添加网站，反向代理到 `http://localhost:5050`。
- 使用 1Panel 的`网站`-`证书`功能为该网站申请免费的 HTTPS 证书。
- 网站开启 HTTPS，选择上一步的证书。

#### 设置502错误页面

在更新网站的过程中，用户会显示502 Bad Gateway错误，因为后端服务还没有启动。可以设置一个自定义的502错误页面，提示用户网站正在维护中，等部署完成后再改回正常页面。

1. 在 1Panel 网站配置的 `server { ... }` 中添加以下内容（放在 `include ... proxy/*.conf` 前面）：

    ```nginx
    error_page 502 503 504 = /502.html;
    location = /502.html {
        internal;
    }
    ```

2. 上传准备好的 `frontend/502.html` 到网站的 `index`（根目录）路径下。

#### 后续更新

当你有新代码提交到 GitHub 后，在服务器上更新：

```bash
# 停止当前运行的容器
docker compose down

# `docker-compose.yml`文件如果修改过端口，这里需要先暂存修改
git stash

# 拉取最新代码（或者手动上传到服务器）
git pull

# `docker-compose.yml` 改回原来的端口映射
git stash pop

# 重启容器
docker compose up -d --build
```


测试git使用