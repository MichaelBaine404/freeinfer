"""
FreeInfer Screenshot Capture
Captures marketing screenshots for Product Hunt, blog posts, and social media.

Prerequisites:
    pip install playwright
    playwright install chromium

Usage:
    Make sure the app is running on :8000 first:
        uvicorn app:app --reload
    Then:
        python scripts/capture_screenshots.py
"""

import os
from pathlib import Path
from playwright.sync_api import sync_playwright


def capture_screenshots():
    """Capture marketing screenshots of FreeInfer."""

    # Create output directory
    output_dir = Path("launch/screenshots")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir.absolute()}")

    base_url = "http://localhost:8000"

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # Screenshot 1: Landing page
        print("\n1. Capturing landing page...")
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(f"{base_url}/")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        page.screenshot(path=str(output_dir / "01_landing.png"), full_page=False)
        print("   Saved: 01_landing.png")
        page.close()

        # Screenshot 2: Chat page with text input (before sending)
        print("\n2. Capturing chat page with input...")
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(f"{base_url}/chat")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        # Type text in the textarea
        page.fill("#userInput", "Write a Python one-liner to flatten a nested list")
        page.wait_for_timeout(500)
        page.screenshot(path=str(output_dir / "02_chat_empty.png"), full_page=False)
        print("   Saved: 02_chat_empty.png")
        page.close()

        # Screenshot 3: Chat page mobile view
        print("\n3. Capturing chat page (mobile)...")
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(f"{base_url}/chat")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        page.screenshot(path=str(output_dir / "03_chat_mobile.png"), full_page=False)
        print("   Saved: 03_chat_mobile.png")
        page.close()

        # Screenshot 4: Docs page
        print("\n4. Capturing docs page...")
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(f"{base_url}/docs-page")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        page.screenshot(path=str(output_dir / "04_docs.png"), full_page=False)
        print("   Saved: 04_docs.png")
        page.close()

        browser.close()

    print("\n✓ All screenshots captured successfully!")
    print(f"Screenshots saved to: {output_dir.absolute()}")


if __name__ == "__main__":
    capture_screenshots()
