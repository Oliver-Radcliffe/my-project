# Pico Beacon - Boot Configuration
# This file runs before main.py on every boot

import gc

# Run garbage collection to free memory
gc.collect()

# Optional: Disable debug REPL on USB for production
# import micropython
# micropython.kbd_intr(-1)

# Print boot message
print("Pico Beacon booting...")
