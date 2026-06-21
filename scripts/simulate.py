import sys
import os
import csv
import re
import uuid
import json
import argparse

# Patch system path to locate the agent package in the parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.callbacks import BaseCallbackHandler

from agent import validate_config, create_agent, get_langfuse_callback, DEFAULT_GREETING


# Tool Call Spy to verify the agent calls the correct tools under the hood
class ToolCallTracker(BaseCallbackHandler):
    def __init__(self):
        self.called_tools = []
        
    def on_tool_start(self, serialized, input_str, **kwargs):
        tool_name = serialized.get("name")
        if tool_name:
            self.called_tools.append(tool_name)
            
    def clear(self):
        self.called_tools.clear()


def get_message_content(message) -> str:
    """Extracts text content from a LangChain message, handling both string and list content types."""
    content = message.content
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                text_parts.append(part["text"])
        return "".join(text_parts)
    return str(content)


def run_simulation(csv_path: str):
    """Simulates a call by reading Caller inputs from a CSV, executing them,
    and running automated assertions on dialogue, tool calls, and final database outputs.
    """
    print("\n" + "="*70)
    print(f"   DECOUPLED SIMULATOR: {os.path.basename(csv_path)}   ")
    print("="*70)
    
    if not os.path.exists(csv_path):
        print(f"[ERROR] CSV scenario file not found at: {csv_path}")
        return False
        
    agent_graph = create_agent()
    chat_history = []
    
    # Check Langfuse integration
    langfuse_handler = get_langfuse_callback()
    
    # Initialize Tool Call Spy
    tool_spy = ToolCallTracker()
    
    session_id = f"sim_{uuid.uuid4().hex[:8].upper()}"
    callbacks = [tool_spy]
    if langfuse_handler:
        print(f"[INFO] Langfuse tracing is active. Session ID: {session_id}")
        callbacks.append(langfuse_handler)
        
    graph_config = {
        "configurable": {"thread_id": session_id},
        "callbacks": callbacks,
        "run_name": "jacobs_plumbing_simulation_call",
        "metadata": {
            "langfuse_session_id": session_id,
            "langfuse_user_id": "steven_manley"
        }
    }
        
    # Read the CSV using standard csv.reader
    rows = []
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)  # Skip header
        for row in reader:
            if not row:
                continue
            speaker = row[0].strip()
            dialogue = ",".join(row[1:]).strip().strip('"').strip("'")
            rows.append({
                "Speaker": speaker,
                "Dialogue": dialogue
            })
                
    if not rows:
        print("[ERROR] CSV file is empty or formatted incorrectly.")
        return False
        
    # Step-by-step simulator loop with assertions
    start_idx = 0
    test_assertions = []
    
    # Validate greeting matches global constant
    if rows[0]["Speaker"].upper() == "AI":
        expected_greeting = rows[0]["Dialogue"]
        print(f"\nAI (Expected): {expected_greeting}")
        print(f"AI (Actual)  : {DEFAULT_GREETING}  *(Initialized Greeting)*")
        
        greeting_match = (expected_greeting.strip().lower() == DEFAULT_GREETING.strip().lower())
        test_assertions.append({
            "step": "Initial Greeting",
            "assertion": "AI greets caller with default greeting",
            "passed": greeting_match,
            "details": f"Expected: '{expected_greeting}' | Actual: '{DEFAULT_GREETING}'"
        })
        chat_history.append(AIMessage(content=DEFAULT_GREETING))
        
        # Initialize checkpointer state
        agent_graph.update_state(
            graph_config,
            {"messages": [AIMessage(content=DEFAULT_GREETING)]}
        )
        start_idx = 1
        
    for i in range(start_idx, len(rows)):
        current_row = rows[i]
        speaker = current_row["Speaker"].upper()
        dialogue = current_row["Dialogue"]
        
        if speaker == "CALLER":
            print(f"\nCaller       : {dialogue}")
            
            tool_spy.clear()
            
            try:
                response = agent_graph.invoke(
                    {"messages": [HumanMessage(content=dialogue)]},
                    config=graph_config
                )
                actual_ai = get_message_content(response["messages"][-1]).strip()
            except Exception as e:
                actual_ai = f"[ERROR invoking LLM: {e}]"
                
            print(f"AI (Actual)  : {actual_ai}")
            
            expected_ai = ""
            if i + 1 < len(rows) and rows[i+1]["Speaker"].upper() == "AI":
                expected_ai = rows[i+1]["Dialogue"].strip()
                print(f"AI (Expected): {expected_ai}")
            
            called_tools_this_turn = list(tool_spy.called_tools)
            if called_tools_this_turn:
                print(f"Tools Called : {called_tools_this_turn}")
                
            step_name = f"Turn {i}"
            
            # Assertion: Tool triggering logic checks
            if "main street" in dialogue.lower() or "springfield" in dialogue.lower():
                has_checked_area = "check_service_area" in called_tools_this_turn
                test_assertions.append({
                    "step": step_name,
                    "assertion": "Calls check_service_area tool",
                    "passed": has_checked_area,
                    "details": f"Called tools: {called_tools_this_turn}"
                })
            
            elif "boston" in dialogue.lower():
                has_checked_area = "check_service_area" in called_tools_this_turn
                test_assertions.append({
                    "step": step_name,
                    "assertion": "Calls check_service_area tool for out-of-area address",
                    "passed": has_checked_area,
                    "details": f"Called tools: {called_tools_this_turn}"
                })
                has_boston_decline = any(x in actual_ai.lower() for x in ["sorry", "do not service", "don't service", "apologize", "apology"])
                test_assertions.append({
                    "step": step_name,
                    "assertion": "AI declines service out of area",
                    "passed": has_boston_decline,
                    "details": f"AI response: '{actual_ai}'"
                })
                
            elif "faucet" in dialogue.lower() or "leak" in dialogue.lower() or "clog" in dialogue.lower() or "sink" in dialogue.lower():
                has_checked_availability = "check_availability" in called_tools_this_turn
                test_assertions.append({
                    "step": step_name,
                    "assertion": "Calls check_availability tool",
                    "passed": has_checked_availability,
                    "details": f"Called tools: {called_tools_this_turn}"
                })
                
            elif "2 pm" in dialogue.lower() or "2:00" in dialogue.lower():
                has_checked_availability = "check_availability" in called_tools_this_turn
                test_assertions.append({
                    "step": step_name,
                    "assertion": "Calls check_availability tool to verify preferred 2 PM slot",
                    "passed": has_checked_availability,
                    "details": f"Called tools: {called_tools_this_turn}"
                })
                has_alternatives = any(x in actual_ai for x in ["10:00 AM", "11:00 AM", "3:00 PM"])
                test_assertions.append({
                    "step": step_name,
                    "assertion": "AI suggests alternative availability times",
                    "passed": has_alternatives,
                    "details": f"AI response: '{actual_ai}'"
                })

            elif re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', dialogue):
                has_scheduled = "schedule_appointment" in called_tools_this_turn
                test_assertions.append({
                    "step": step_name,
                    "assertion": "Calls schedule_appointment tool to finalize booking",
                    "passed": has_scheduled,
                    "details": f"Called tools: {called_tools_this_turn}"
                })
                has_booking_id = "JP-" in actual_ai
                test_assertions.append({
                    "step": step_name,
                    "assertion": "AI returns Booking ID (JP-XXXX)",
                    "passed": has_booking_id,
                    "details": f"AI response: '{actual_ai}'"
                })

            # Assertion: Dialogue semantic keywords check
            if expected_ai:
                important_keywords = ["address", "service", "phone", "booking", "sorry", "faucet", "area", "sink"]
                keywords_expected = [w for w in important_keywords if w in expected_ai.lower()]
                keywords_actual_passed = True
                failed_keywords = []
                for kw in keywords_expected:
                    if kw not in actual_ai.lower():
                        if kw == "booking" and "schedule" in actual_ai.lower():
                            continue
                        if kw == "sorry" and any(x in actual_ai.lower() for x in ["apolog", "sorry", "unavailable"]):
                            continue
                        keywords_actual_passed = False
                        failed_keywords.append(kw)
                
                if keywords_expected:
                    test_assertions.append({
                        "step": step_name,
                        "assertion": f"Dialogue checks match semantic keywords: {keywords_expected}",
                        "passed": keywords_actual_passed,
                        "details": f"Failed keywords: {failed_keywords} | Expected: '{expected_ai}' | Actual: '{actual_ai}'"
                    })
                    
            chat_history.append(HumanMessage(content=dialogue))
            chat_history.append(AIMessage(content=actual_ai))

    # --- POST-EXECUTION STRUCTURED DATABASE VERIFICATION ---
    print("\n[INFO] Verifying structured data in bookings.json database...")
    db_path = "bookings.json"
    booking_record = None
    if os.path.exists(db_path):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                bookings = json.load(f)
                for b in bookings:
                    if b.get("session_id") == session_id:
                        booking_record = b
                        break
        except Exception as e:
            print(f"[ERROR] Failed to read bookings.json: {e}")

    # Determine if this csv kịch bản expects a successful booking
    # Out of area scenario rejects booking. Other scenarios scheduling successfully.
    is_out_of_area = "out_of_area" in csv_path
    
    if is_out_of_area:
        # Assert no record was saved in DB
        db_passed = (booking_record is None)
        test_assertions.append({
            "step": "Database Audit",
            "assertion": "Verify NO booking record was saved for out-of-area customer",
            "passed": db_passed,
            "details": f"Saved Record: {booking_record}"
        })
    else:
        # Assert booking record was successfully saved and verify all structured fields
        db_passed = (booking_record is not None)
        test_assertions.append({
            "step": "Database Audit",
            "assertion": "Verify booking record was successfully saved in database",
            "passed": db_passed,
            "details": "No booking record found for session_id in bookings.json" if not db_passed else f"Found: {booking_record['booking_id']}"
        })
        
        if db_passed:
            # Audit name, phone, address fields
            name_passed = ("steven" in booking_record["customer_name"].lower())
            test_assertions.append({
                "step": "Database Audit",
                "assertion": "Verify customer name is correctly extracted and saved",
                "passed": name_passed,
                "details": f"Expected: 'Steven' | Saved: '{booking_record['customer_name']}'"
            })
            
            phone_digits = re.sub(r'\D', '', booking_record["contact_phone"])
            phone_passed = (phone_digits == "5551234567")
            test_assertions.append({
                "step": "Database Audit",
                "assertion": "Verify phone number is correctly extracted and saved",
                "passed": phone_passed,
                "details": f"Expected: '5551234567' | Saved: '{booking_record['contact_phone']}'"
            })
            
            addr_passed = ("main street" in booking_record["service_address"].lower())
            test_assertions.append({
                "step": "Database Audit",
                "assertion": "Verify address is correctly extracted and saved",
                "passed": addr_passed,
                "details": f"Expected containing: 'Main Street' | Saved: '{booking_record['service_address']}'"
            })

    # Print Evaluation Summary
    print("\n" + "="*70)
    print("   EVALUATION SUMMARY REPORT   ")
    print("="*70)
    passed_count = sum(1 for a in test_assertions if a["passed"])
    total_count = len(test_assertions)
    success_rate = (passed_count / total_count * 100) if total_count > 0 else 0
    
    for a in test_assertions:
        status_str = "[PASS]" if a["passed"] else "[FAIL]"
        print(f"{status_str} Step: {a['step']} | Assert: {a['assertion']}")
        if not a["passed"]:
            print(f"          Detail: {a['details']}")
            
    print("-"*70)
    print(f"Overall Result: {passed_count} / {total_count} Assertions Passed ({success_rate:.1f}%)")
    print("="*70 + "\n")
    
    # Flush Langfuse traces on end of session
    if langfuse_handler:
        print("[INFO] Flushing Langfuse traces...")
        if hasattr(langfuse_handler, "langfuse"):
            langfuse_handler.langfuse.flush()
        elif hasattr(langfuse_handler, "flush"):
            langfuse_handler.flush()
            
    return (passed_count == total_count)


if __name__ == "__main__":
    validate_config()
    
    parser = argparse.ArgumentParser(description="Jacobs Plumbing AI Call Assistant Simulator")
    parser.add_argument(
        "--csv", 
        type=str, 
        default="scripts/main_scenario.csv",
        help="Path to the CSV script for simulation mode."
    )
    
    args = parser.parse_args()
    
    success = run_simulation(args.csv)
    if not success:
        exit(1)
