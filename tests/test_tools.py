import unittest
from agent.tools import check_service_area, check_availability, schedule_appointment

class TestPlumbingTools(unittest.TestCase):
    
    def test_check_service_area_valid(self):
        """Test serviced area logic with word boundary matching."""
        # Using .invoke because these are LangChain Tool instances
        self.assertTrue(check_service_area.invoke("123 Main Street, Springfield"))
        self.assertTrue(check_service_area.invoke("Main Street"))
        self.assertTrue(check_service_area.invoke("springfield, IL"))
        
    def test_check_service_area_invalid(self):
        """Test out of service area addresses, including brittle edge cases."""
        self.assertFalse(check_service_area.invoke("456 Oak Road, Boston"))
        self.assertFalse(check_service_area.invoke("Springfieldville"))  # Substring matches but not word boundary
        self.assertFalse(check_service_area.invoke("Main Streetville"))
        
    def test_check_service_area_empty(self):
        """Test that empty inputs raise ValueError."""
        with self.assertRaises(ValueError):
            check_service_area.invoke("")
        with self.assertRaises(ValueError):
            check_service_area.invoke("   ")

    def test_check_availability_available(self):
        """Test slots that are open (should return empty list)."""
        alternates = check_availability.invoke({"date": "Monday", "time": "10 AM"})
        self.assertEqual(alternates, [])
        
    def test_check_availability_busy(self):
        """Test slots that are busy (like 2 PM, should return alternatives)."""
        alternates = check_availability.invoke({"date": "Monday", "time": "2 PM"})
        self.assertIn("10:00 AM", alternates)
        self.assertIn("11:00 AM", alternates)
        self.assertIn("3:00 PM", alternates)
        
    def test_check_availability_sunday(self):
        """Test Sunday slot (closed, should return alternative slots)."""
        alternates = check_availability.invoke({"date": "Sunday", "time": "10 AM"})
        self.assertTrue(len(alternates) > 0)
        self.assertIn("Monday at 10:00 AM", alternates)
        
    def test_check_availability_empty(self):
        """Test that empty fields raise ValueError."""
        with self.assertRaises(ValueError):
            check_availability.invoke({"date": "", "time": "10 AM"})
        with self.assertRaises(ValueError):
            check_availability.invoke({"date": "Monday", "time": "   "})

    def test_schedule_appointment_success(self):
        """Test booking successfully creates a unique JP ID and saves details."""
        res = schedule_appointment.invoke({
            "name": "Steven Manley",
            "address": "123 Main Street",
            "phone": "5551234567",
            "service": "leaky faucet",
            "date": "tomorrow",
            "time": "10 AM"
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["customer_name"], "Steven Manley")
        self.assertTrue(res["booking_id"].startswith("JP-"))
        self.assertEqual(len(res["booking_id"]), 11) # "JP-" + 8 char hex

    def test_schedule_appointment_validation(self):
        """Test that validation triggers errors for empty fields or bad phone numbers."""
        # Empty fields
        with self.assertRaises(ValueError):
            schedule_appointment.invoke({
                "name": "",
                "address": "123 Main Street",
                "phone": "5551234567",
                "service": "leaky faucet",
                "date": "tomorrow",
                "time": "10 AM"
            })
            
        # Bad phone number format
        with self.assertRaises(ValueError):
            schedule_appointment.invoke({
                "name": "Steven",
                "address": "123 Main Street",
                "phone": "555-abc",  # contains non-digits
                "service": "leaky faucet",
                "date": "tomorrow",
                "time": "10 AM"
            })
            
        # Too short phone number
        with self.assertRaises(ValueError):
            schedule_appointment.invoke({
                "name": "Steven",
                "address": "123 Main Street",
                "phone": "12345",  # < 7 digits
                "service": "leaky faucet",
                "date": "tomorrow",
                "time": "10 AM"
            })

if __name__ == "__main__":
    unittest.main()
