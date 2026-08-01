import shutil
from pathlib import Path

target = Path("/opt/jarvis-core/owner_tools.py")
backup = target.with_suffix(".py.bak.payment_tool_add")
shutil.copy(target, backup)
print(f"Backed up to {backup}")

src = target.read_text()

old_schema_close = '''                "required": ["vendor_category", "product_details"],
            },
        },
    },
]'''

new_schema_close = '''                "required": ["vendor_category", "product_details"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_payment_reminder",
            "description": (
                "Send a payment reminder to a customer with a pending "
                "invoice. Only call this when the owner CLEARLY asks to "
                "send/follow up on a payment or invoice for a named "
                "customer -- not for ordinary catalog or vendor requests."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {"type": "string", "description": "Customer's name as the owner referred to them"},
                    "invoice_no": {"type": "string", "description": "Invoice number, omit if not mentioned"},
                },
                "required": ["customer_name"],
            },
        },
    },
]'''

assert old_schema_close in src, "schema close not found -- aborting"
src = src.replace(old_schema_close, new_schema_close, 1)

old_prompt = '''OWNER_TOOL_SYSTEM_PROMPT = (
    "You are helping the owner of this business manage requests. You have "
    "one tool available: forwarding a requirement to a vendor. Only call "
    "it when they clearly mean 'forward/send/pass this to X' — for "
    "anything else (catalog questions, casual conversation, anything you "
    "don't have a tool for), do NOT call a tool; a different response "
    "path handles that."
)'''

new_prompt = '''OWNER_TOOL_SYSTEM_PROMPT = (
    "You are helping the owner of this business manage requests. You have "
    "two tools available: forwarding a requirement to a vendor, and "
    "sending a payment reminder to a customer. Only call a tool when the "
    "owner CLEARLY means one of these two things — for anything else "
    "(catalog questions, casual conversation, anything you don't have a "
    "tool for), do NOT call a tool; a different response path handles that."
)'''

assert old_prompt in src, "system prompt not found -- aborting"
src = src.replace(old_prompt, new_prompt, 1)

old_dispatch = '''    if name == "forward_to_vendor":
        return await forward_to_vendor(tenant, requester_name=requester_name, **args)

    return None'''

new_dispatch = '''    if name == "forward_to_vendor":
        return await forward_to_vendor(tenant, requester_name=requester_name, **args)

    if name == "send_payment_reminder":
        from payment_tools import send_payment_reminder
        return await send_payment_reminder(tenant, **args)

    return None'''

assert old_dispatch in src, "dispatch block not found -- aborting"
src = src.replace(old_dispatch, new_dispatch, 1)

target.write_text(src)
print("Patched: send_payment_reminder wired into owner tool dispatch.")
