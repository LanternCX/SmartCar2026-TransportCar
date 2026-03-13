import gc, sys

gc.collect()
for n in tuple(sys.modules):
    if n.startswith("services.stage2_smoke") or n.startswith(
        "services.commanding.handlers"
    ):
        del sys.modules[n]
__import__("services.stage2_smoke")
m = sys.modules["services.stage2_smoke"]
print(m._collect_lite_transport_summary())
