import re

from app.locales import de, en, uz

PLACEHOLDER = re.compile(r"{(\w+)}")


def main() -> None:
    base = en.MESSAGES
    ok = True
    for name, module in (("uz", uz), ("de", de)):
        messages = module.MESSAGES
        for key in sorted(base.keys() - messages.keys()):
            print(f"❌ {name}: missing key {key}")
            ok = False
        for key in sorted(messages.keys() - base.keys()):
            print(f"⚠️ {name}: extra key {key}")
        for key in sorted(base.keys() & messages.keys()):
            if set(PLACEHOLDER.findall(base[key])) != set(PLACEHOLDER.findall(messages[key])):
                print(f"❌ {name}: placeholders differ in {key}")
                ok = False
    print("✅ All translations are complete" if ok else "Fix the problems above.")


main()