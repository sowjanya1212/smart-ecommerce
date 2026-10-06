p = "shop/admin.py"
s = open(p, encoding="utf-8").read()

if "orders are created by customers" in s:
    print("Already patched - restart the server.")
else:
    start = s.index("class OrderAdmin")
    key = 'staff_can = ("view", "change")\n'
    i = s.index(key, start) + len(key)
    s = s[:i] + (
        "\n    def has_add_permission(self, request, obj=None):\n"
        "        return False  # orders are created by customers via checkout\n"
    ) + s[i:]
    open(p, "w", encoding="utf-8").write(s)
    print("Patched OK")