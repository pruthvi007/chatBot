from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet, EventType
from rasa_sdk.executor import CollectingDispatcher
from actions.database_connectivity import DataUpdate

class ValidateJobForm(Action):
    def name(self) -> Text:
        return "user_details_form" 
        
    def run(
            self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[EventType]:
        required_slots = ["name", "num" ,"mail"] 
                          
        for slot_name in required_slots:
            if tracker.slots.get(slot_name) is None:
                return [SlotSet("requested_slot", slot_name)] 

class ActionSubmit(Action):
    def name(self) -> Text:
        return "action_submit" 


    def run(
        self,
        dispatcher,
        tracker: Tracker,
         domain: "Dict",
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(template="utter_details_thanks",name=tracker.get_slot("name"),num=tracker.get_slot("num"),mail=tracker.get_slot("mail")) 
        DataUpdate(tracker.get_slot("name"),tracker.get_slot("num"),tracker.get_slot("mail"))