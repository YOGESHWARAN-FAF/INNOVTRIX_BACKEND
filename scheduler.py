import os
import time
from datetime import datetime
from firebase_admin import db
from app.services.msg import send_notification

def run_scheduler():
    while True:
        now = datetime.now().strftime("%I:%M %p")
        users_ref = db.reference("users")
        users = users_ref.get() or {}

        for uid, user_data in users.items():
            schedules = user_data.get("schedules", {})
            venues = user_data.get("venues", {})

            # ---- Schedule trigger (modified with one-time logic) ----
            for venue, schedule_devices in schedules.items():
                for device, sch in schedule_devices.items():

                    if sch.get("status") == "enable" and sch.get("time") == now:
                        action = sch.get("action")

                        last_sent = sch.get("lastNotified")
                        current_ts = int(time.time())

                        # send only once per hour
                        if not last_sent or current_ts - int(last_sent) >= 3600:

                            # Perform device state update
                            db.reference(f"users/{uid}/venues/{venue}/{device}").set(action)

                            # Send schedule completed notification
                            send_notification(uid, "Schedule Completed ⏱️",
                                              f"{device} in {venue} set to {action}")

                            # Save timestamp to schedule entry
                            db.reference(f"users/{uid}/schedules/{venue}/{device}").update({
                                "lastNotified": current_ts
                            })
                        # else:
                        #     pass # Cooldown active

            # ---- Fault Notification (once per hour only) ----
            faults = ""
            fault_venue = None

            for vname, vdata in venues.items():
                if isinstance(vdata, dict) and "faults" in vdata:
                    faults = vdata["faults"]
                    fault_venue = vname
                    break

            if faults:
                user_ref = db.reference(f"users/{uid}")
                last_sent = user_ref.child("lastFaultNotification").get()
                current_ts = int(time.time())

                # Send only once per hour
                if not last_sent or current_ts - last_sent >= 3600:
                    send_notification(uid, "Fault Detected ⚠️", faults)
                    # Save timestamp
                    user_ref.update({"lastFaultNotification": current_ts})
                # else:
                #     pass # Cooldown active

        time.sleep(5)
