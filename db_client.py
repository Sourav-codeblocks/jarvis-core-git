"""Jarvis Core — shared Supabase client factory.

Pulled out of main.py so certify_model.py and llm_router.py don't each
create their own client / re-read env vars independently.
"""

import os
from functools import lru_cache
from supabase import create_client


@lru_cache(maxsize=1)
def get_supabase():
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SECRET_KEY"],
    )
