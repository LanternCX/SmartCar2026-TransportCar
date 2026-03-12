import gc, sys

gc.collect()
__import__("services.stage2_smoke_lite")
m = sys.modules["services.stage2_smoke_lite"]
print(
    m.collect_lite_transport_summary(
        ("health", "tick", "imu", "enc", "motor", "vision", "pos", "lock", "log"),
        m.check_transport_source,
    )
)
