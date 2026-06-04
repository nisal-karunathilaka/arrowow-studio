import os

class ApprovalGate:
    @staticmethod
    def prompt(gate_name: str, context_message: str) -> str:
        print(f"\n{'='*50}")
        print(f" GATE: {gate_name}")
        print(f"{'='*50}")
        print(context_message)
        print("\nOptions:")
        print("[Y] Approve and Proceed")
        print("[R] Request Revision")
        print("[S] Skip Stage")
        print("[A] Abort Production")
        
        if os.environ.get("AUTO_APPROVE") == "1":
            print("AUTO_APPROVE=1 detected. Auto-approving with [Y].")
            return "Y"
            
        while True:
            choice = input("Enter choice (Y/R/S/A): ").strip().upper()
            if choice in ['Y', 'R', 'S', 'A']:
                return choice
            print("Invalid choice. Please enter Y, R, S, or A.")
