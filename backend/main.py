import os
import sys
import subprocess

PROJECT_NAME = "SafeSight: Intelligent Threat Surveillance System"
DEVELOPER_NAME = "Ashish"
INSTITUTION = "Sir M. Visvesvaraya Institute of Technology (SMVIT)"
VERSION = "v1.2.0"

def print_banner():
    os.system("cls" if os.name == "nt" else "clear")
    print("=" * 65)
    print(f"  {PROJECT_NAME}")
    print(f"  Lead Developer : {DEVELOPER_NAME}")
    print(f"  Institution    : {INSTITUTION}")
    print(f"  System Build   : {VERSION}")
    print("=" * 65)
    print("\nSelect an operational module to launch:\n")
    print("  [1] Launch Live Surveillance Engine (safesight.py)")
    print("  [2] Start Security Web Dashboard (dashboard.py)")
    print("  [3] Run Restricted Zone Module (restricted_zone.py)")
    print("  [4] Run Crowd Gathering Module (crowd_detection.py)")
    print("  [5] Run Abandoned Luggage Detection (abandoned_bag.py)")
    print("  [6] Check / Reset SQLite Database (safesight.db)")
    print("  [0] Exit")
    print("-" * 65)

def main():
    while True:
        print_banner()
        choice = input("Enter option [0-6]: ").strip()

        if choice == "1":
            print("\nStarting SafeSight Vision Engine...")
            subprocess.run([sys.executable, "backend/safesight.py"])
        elif choice == "2":
            print("\nStarting Streamlit Dashboard on http://localhost:8501...")
            subprocess.run(["streamlit", "run", "backend/dashboard.py"])
        elif choice == "3":
            print("\nLaunching Restricted Zone Module...")
            subprocess.run([sys.executable, "backend/restricted_zone.py"])
        elif choice == "4":
            print("\nLaunching Crowd Gathering Module...")
            subprocess.run([sys.executable, "backend/crowd_detection.py"])
        elif choice == "5":
            print("\nLaunching Abandoned Luggage Module...")
            subprocess.run([sys.executable, "backend/abandoned_bag.py"])
        elif choice == "6":
            db_file = "safesight.db"
            if os.path.exists(db_file):
                size_kb = os.path.getsize(db_file) / 1024
                print(f"\nDatabase status: Active ({size_kb:.2f} KB)")
                confirm = input("Would you like to clear historical records? (y/n): ").strip().lower()
                if confirm == "y":
                    os.remove(db_file)
                    print("Database reset successfully.")
            else:
                print("\nDatabase file not created yet.")
            input("\nPress Enter to return to menu...")
        elif choice == "0":
            print("\nExiting SafeSight. Goodbye!")
            break
        else:
            input("\nInvalid selection. Press Enter to retry...")

if __name__ == "__main__":
    main()