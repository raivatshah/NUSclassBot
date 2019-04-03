# NUSclassBot

A simple telegram bot that allows students to seamlessly mark their attendance for different NUS Mods. The following commands/features are supported: 

---

## Tutor Side

1. `/setup_sheet` prompts the tutor to use the device's brower to login into their Google account and obtain an auth token for the bot to create and update Google sheets on their behalf. 
1. `/setup_sheet <auth token>` sets up a Google Sheet for a particular session. This is a prerequisite for the following `/start_session` command. 
1. `/start_session <num students>` setups up a "session" of `num students` size. A session refers to a period during which the bot accepts `/attend` requests from students upto its size. 
1. `/stop_session` stops a session. 

---

## Student Side 

1. `/setup` is a command to register the student on the bot. Student is then prompted to enter their full name as per IVLE/NUS records. This is a prerequisite for the the following `/attend` command. 
1. `/attend <att token>` marks the attendance of the sender if i) the session is not at full capacity and ii) the token is correct. In any other cases, the bot responds to the user with an appropriate error message. 

---

Please let anyone of us know if you find any bugs or would like to suggest improvements or have feedback! Thank you for using the bot!
