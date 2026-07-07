from tortoise import fields
from tortoise.models import Model


class HardwareProfile(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100, unique=True)
    description = fields.TextField(null=True)
    is_default = fields.BooleanField(default=False)

    board_name = fields.CharField(max_length=100, null=True)
    board_serial = fields.CharField(max_length=100, null=True)

    bit_file = fields.CharField(max_length=500, null=True)
    bit_program_channel = fields.CharField(max_length=100, null=True)

    elf_file = fields.CharField(max_length=500, null=True)
    jlink_serial = fields.CharField(max_length=100, null=True)
    jlink_interface = fields.CharField(max_length=50, null=True)
    jlink_device = fields.CharField(max_length=100, null=True)
    jlink_speed_khz = fields.IntField(null=True)

    uart_port = fields.CharField(max_length=100, null=True)
    uart_baudrate = fields.IntField(default=115200)
    uart_bytesize = fields.IntField(default=8)
    uart_parity = fields.CharField(max_length=20, default="N")
    uart_stopbits = fields.FloatField(default=1.0)
    uart_timeout_ms = fields.IntField(default=1000)

    scope_model = fields.CharField(max_length=100, null=True)
    scope_ip = fields.CharField(max_length=100, null=True)
    scope_port = fields.IntField(null=True)
    scope_channel = fields.CharField(max_length=50, null=True)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    resources: fields.ReverseRelation["HardwareResource"]

    class Meta:
        table = "hardware_profiles"

    def __str__(self):
        return self.name


class HardwareResource(Model):
    id = fields.IntField(pk=True)

    profile = fields.ForeignKeyField(
        "models.HardwareProfile",
        related_name="resources",
        on_delete=fields.CASCADE,
    )

    name = fields.CharField(max_length=100)
    type = fields.CharField(max_length=50)
    config_json = fields.JSONField()
    enabled = fields.BooleanField(default=True)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "hardware_resources"
        unique_together = (("profile", "name"),)

    def __str__(self):
        return f"{self.profile_id}:{self.name}"


class TestCase(Model):
    id = fields.IntField(pk=True)

    name = fields.CharField(max_length=100, unique=True)
    type = fields.CharField(max_length=80, null=True)
    description = fields.TextField(null=True)
    config_json = fields.JSONField(null=True)
    enabled = fields.BooleanField(default=True)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    plan_links: fields.ReverseRelation["TestPlanCase"]
    results: fields.ReverseRelation["TestCaseResult"]

    class Meta:
        table = "test_cases"

    def __str__(self):
        return self.name


class TestStep(Model):
    id = fields.IntField(pk=True)

    case = fields.ForeignKeyField(
        "models.TestCase",
        related_name="steps",
        on_delete=fields.CASCADE,
    )

    order_index = fields.IntField(default=0)
    step_type = fields.CharField(max_length=50)
    name = fields.CharField(max_length=100)
    config_json = fields.JSONField(default=dict)
    expected_json = fields.JSONField(default=dict)
    timeout_ms = fields.IntField(default=30000)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    results: fields.ReverseRelation["TestStepResult"]

    class Meta:
        table = "test_steps"
        unique_together = (("case", "order_index"),)

    def __str__(self):
        return f"{self.case_id}:{self.order_index}:{self.name}"


class TestPlan(Model):
    id = fields.IntField(pk=True)

    name = fields.CharField(max_length=100, unique=True)
    board = fields.CharField(max_length=100, null=True)
    description = fields.TextField(null=True)
    setup_json = fields.JSONField(null=True)
    enabled = fields.BooleanField(default=True)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    case_links: fields.ReverseRelation["TestPlanCase"]
    runs: fields.ReverseRelation["TestRun"]

    class Meta:
        table = "test_plans"

    def __str__(self):
        return self.name


class TestPlanCase(Model):
    id = fields.IntField(pk=True)

    plan = fields.ForeignKeyField(
        "models.TestPlan",
        related_name="case_links",
        on_delete=fields.CASCADE,
    )

    case = fields.ForeignKeyField(
        "models.TestCase",
        related_name="plan_links",
        on_delete=fields.CASCADE,
    )

    run_order = fields.IntField(default=0)
    enabled = fields.BooleanField(default=True)

    class Meta:
        table = "test_plan_cases"
        unique_together = (("plan", "case"),)


class TestRun(Model):
    id = fields.IntField(pk=True)

    plan = fields.ForeignKeyField(
        "models.TestPlan",
        related_name="runs",
        null=True,
        on_delete=fields.SET_NULL,
    )

    hardware_profile = fields.ForeignKeyField(
        "models.HardwareProfile",
        related_name="runs",
        null=True,
        on_delete=fields.SET_NULL,
    )

    test_case = fields.ForeignKeyField(
        "models.TestCase",
        related_name="runs",
        null=True,
        on_delete=fields.SET_NULL,
    )

    name = fields.CharField(max_length=150, null=True)
    status = fields.CharField(max_length=50, default="pending")
    result = fields.CharField(max_length=50, null=True)
    summary = fields.TextField(null=True)
    error_message = fields.TextField(null=True)

    selected_case_ids_json = fields.JSONField(null=True)
    profile_snapshot_json = fields.JSONField(null=True)
    case_snapshot_json = fields.JSONField(null=True)

    started_at = fields.DatetimeField(null=True)
    finished_at = fields.DatetimeField(null=True)
    duration_ms = fields.IntField(null=True)
    ended_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    step_results: fields.ReverseRelation["TestStepResult"]
    case_results: fields.ReverseRelation["TestCaseResult"]
    logs: fields.ReverseRelation["TestLog"]

    class Meta:
        table = "test_runs"


class TestStepResult(Model):
    id = fields.IntField(pk=True)

    run = fields.ForeignKeyField(
        "models.TestRun",
        related_name="step_results",
        on_delete=fields.CASCADE,
    )

    test_step = fields.ForeignKeyField(
        "models.TestStep",
        related_name="results",
        null=True,
        on_delete=fields.SET_NULL,
    )

    order_index = fields.IntField(default=0)
    step_name = fields.CharField(max_length=100, null=True)
    step_type = fields.CharField(max_length=50, null=True)
    name = fields.CharField(max_length=100, null=True)
    type = fields.CharField(max_length=80, null=True)

    status = fields.CharField(max_length=50, default="pending")
    result = fields.CharField(max_length=50, null=True)
    message = fields.TextField(null=True)
    stdout = fields.TextField(null=True)
    stderr = fields.TextField(null=True)
    data_json = fields.JSONField(null=True)
    log = fields.TextField(null=True)

    started_at = fields.DatetimeField(null=True)
    finished_at = fields.DatetimeField(null=True)
    duration_ms = fields.IntField(null=True)
    ended_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "test_step_results"


class TestCaseResult(Model):
    id = fields.IntField(pk=True)

    run = fields.ForeignKeyField(
        "models.TestRun",
        related_name="case_results",
        on_delete=fields.CASCADE,
    )

    case = fields.ForeignKeyField(
        "models.TestCase",
        related_name="results",
        null=True,
        on_delete=fields.SET_NULL,
    )

    case_name = fields.CharField(max_length=100)
    case_type = fields.CharField(max_length=80)

    status = fields.CharField(max_length=50, default="pending")
    result = fields.CharField(max_length=50, null=True)
    log = fields.TextField(null=True)

    started_at = fields.DatetimeField(null=True)
    ended_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "test_case_results"


class TestLog(Model):
    id = fields.IntField(pk=True)

    run = fields.ForeignKeyField(
        "models.TestRun",
        related_name="logs",
        null=True,
        on_delete=fields.CASCADE,
    )

    case_result = fields.ForeignKeyField(
        "models.TestCaseResult",
        related_name="logs",
        null=True,
        on_delete=fields.CASCADE,
    )

    level = fields.CharField(max_length=20, default="INFO")
    source = fields.CharField(max_length=100, null=True)
    message = fields.TextField()

    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "test_logs"
