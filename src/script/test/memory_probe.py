"""板端裸内存探针."""

import gc


def _print_memory(tag):
    collect = getattr(gc, "collect", None)
    if collect is not None:
        collect()
    mem_free = getattr(gc, "mem_free", None)
    mem_alloc = getattr(gc, "mem_alloc", None)
    if mem_free is None or mem_alloc is None:
        print("mem %s na" % tag)
        return
    free_value = int(mem_free())
    alloc_value = int(mem_alloc())
    print("mem %s f=%d a=%d t=%d" % (tag, free_value, alloc_value, free_value + alloc_value))


def main():
    _print_memory("before")
    _print_memory("after")
    return True


if globals().get("__spec__") is None:
    main()
