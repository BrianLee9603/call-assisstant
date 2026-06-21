import re
import uuid
import logging
from langchain_core.tools import tool

# Set up logging for tools observability
logger = logging.getLogger("agent.tools")

@tool
def check_service_area(address: str) -> bool:
    """Checks if the customer's address is within the service area of Jacobs Plumbing.
    
    Args:
        address (str): The customer's full address.
        
    Returns:
        bool: True if the area is serviced, False if it is out of the service area.
    """
    logger.info(f"check_service_area called with address: '{address}'")
    
    if not address or not address.strip():
        logger.warning("Empty address provided to check_service_area")
        raise ValueError("Address cannot be empty.")
        
    # Normalize address for matching
    addr_lower = address.lower().strip()
    
    # Improved matching: Use regex word boundaries to prevent false positives
    # e.g., matching "Springfieldville" or "Springfield Mall, Denver"
    is_serviced = bool(re.search(r'\bspringfield\b', addr_lower) or re.search(r'\bmain street\b', addr_lower))
    
    logger.info(f"Service area check result for '{address}': {is_serviced}")
    
    # PRODUCTION NOTE: Naive regex/substring matching is brittle for address parsing.
    # In a production environment, this should interface with a Geocoding API 
    # (e.g., Google Maps Address Validation API or Geocoding API) to validate 
    # the address format, extract the city/postal code components, and check 
    # if it falls within service boundary coordinates.
    
    return is_serviced


@tool
def check_availability(date: str, time: str) -> list[str]:
    """Checks if a preferred booking date and time are available for a technician.
    
    If the requested slot is available, it returns an empty list.
    If the requested slot is unavailable, it returns a list of alternative times.
    
    Args:
        date (str): The date of the appointment (e.g. 'tomorrow', 'Sunday', '2026-06-22').
        time (str): The preferred time of the appointment (e.g. '10 AM', '2 PM').
        
    Returns:
        list[str]: Empty list if available, or a list of available alternative time slots.
    """
    logger.info(f"check_availability called with date: '{date}', time: '{time}'")
    
    if not date or not date.strip():
         raise ValueError("Date cannot be empty.")
    if not time or not time.strip():
         raise ValueError("Time cannot be empty.")
         
    # Normalize parameters
    date_lower = date.lower().strip()
    time_lower = time.lower().strip()
    
    # 1. Date-aware validation: Sunday is closed
    if "sunday" in date_lower:
        logger.info("Service requested on a Sunday (closed). Suggesting Monday slots.")
        return ["Monday at 10:00 AM", "Monday at 11:00 AM", "Monday at 3:00 PM"]
        
    # 2. Time-aware validation: 2 PM / 14:00 is busy
    if "2 pm" in time_lower or "2:00" in time_lower or "14:00" in time_lower:
        logger.info(f"Preferred time '{time}' is busy on '{date}'. Returning alternates.")
        return ["10:00 AM", "11:00 AM", "3:00 PM"]
    
    # Any other time is available
    logger.info(f"Preferred slot '{date} at {time}' is available.")
    return []


import json
import os
import datetime
from langchain_core.runnables import RunnableConfig

@tool
def schedule_appointment(
    name: str, 
    address: str, 
    phone: str, 
    service: str, 
    date: str, 
    time: str,
    config: RunnableConfig = None
) -> dict:
    """Schedules a plumbing appointment in the database with customer and job details.
    
    Args:
        name (str): The customer's name.
        address (str): The service address.
        phone (str): The customer's phone number.
        service (str): A description of the service requested (e.g., 'leaky faucet').
        date (str): The agreed-upon date.
        time (str): The agreed-upon time.
        
    Returns:
        dict: A dictionary containing booking status, message, and booking_id.
    """
    logger.info(f"schedule_appointment request for customer '{name}' at '{address}'")
    
    # Input Validation
    errors = []
    if not name or not name.strip():
        errors.append("Customer name is required.")
    if not address or not address.strip():
        errors.append("Service address is required.")
    if not phone or not phone.strip():
        errors.append("Phone number is required.")
    else:
        # Strip all non-digit characters to count the actual digits
        digits_only = re.sub(r'\D', '', phone)
        if len(digits_only) < 7:
            errors.append("Invalid phone number format. Must contain at least 7 digits.")
    if not service or not service.strip():
        errors.append("Service description is required.")
    if not date or not date.strip():
        errors.append("Appointment date is required.")
    if not time or not time.strip():
        errors.append("Appointment time is required.")
        
    if errors:
        logger.warning(f"Validation failed for schedule_appointment: {errors}")
        raise ValueError(f"Validation errors: {'; '.join(errors)}")
        
    # Generate unique, collision-free booking ID using UUID (Senior review recommendation)
    booking_id = f"JP-{uuid.uuid4().hex[:8].upper()}"
    
    logger.info(f"Appointment successfully scheduled. Booking ID: {booking_id}")
    
    # Extract session_id dynamically from the RunnableConfig context if available
    session_id = "unknown_session"
    if config:
        metadata = config.get("metadata", {}) or {}
        configurable = config.get("configurable", {}) or {}
        session_id = metadata.get("langfuse_session_id") or configurable.get("thread_id", "unknown_session")
        
    # Save booking entry to mock database file bookings.json
    booking_entry = {
        "booking_id": booking_id,
        "customer_name": name.strip(),
        "service_address": address.strip(),
        "contact_phone": phone.strip(),
        "service_type": service.strip(),
        "appointment_date": date.strip(),
        "appointment_time": time.strip(),
        "session_id": session_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    
    db_path = "bookings.json"
    bookings_list = []
    if os.path.exists(db_path):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                bookings_list = json.load(f)
                if not isinstance(bookings_list, list):
                    bookings_list = []
        except Exception:
            bookings_list = []
            
    bookings_list.append(booking_entry)
    try:
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(bookings_list, f, indent=4, ensure_ascii=False)
        logger.info(f"Booking {booking_id} saved to {db_path} under session {session_id}")
    except Exception as e:
        logger.error(f"Failed to write to mock database {db_path}: {e}")
    
    return {
        "status": "SUCCESS",
        "booking_id": booking_id,
        "customer_name": name.strip(),
        "service_address": address.strip(),
        "contact_phone": phone.strip(),
        "service_type": service.strip(),
        "appointment_date": date.strip(),
        "appointment_time": time.strip(),
        "message": f"Appointment successfully scheduled with ID {booking_id}."
    }

# Export the list of tools
tools_list = [check_service_area, check_availability, schedule_appointment]
