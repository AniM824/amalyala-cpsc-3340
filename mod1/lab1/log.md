# Lab 1 Log — Raspberry Pi Setup (CPSC 3340)

| Time | Entry |
|------|-------|
| 13:59 | Finished reading through the instructions. |
| 14:05 | Connected the Pi in the correct order, but the display didn't work. |
| 14:07 | Realized it is a problem with the case → switched to a Pi 4. |
| 14:09 | HDMI connection works now. |
| 14:10 | SSH-ed into the Pi after finding its IP address with `ifconfig`. |
| 14:13 | Created a passphraseless SSH key, following the official GitHub instructions. |
| 14:14 | Added the public SSH key to my GitHub profile. |
| 14:16 | Used `ssh-copy-id` for key-based SSH access, instead of having to type the username and password every time. |
| 14:17 | Started researching how to run a script automatically once the connection is established. |
| 14:21 | Decided to try a systemd **user** service. |
| 14:23 | Never mind — this didn't make sense: the IP update needs to happen on boot, so a **system** service is what we need. |
| 14:25 | Installed vim on the Pi for easier editing. |
| 14:26–14:30 | Decided on the folder structure: `CPSC3340` repo in the user root → `rpi` → `[boot, copyconfig.sh, ip.md]`. Touched `copyconfig.service` and `copyconfig.sh`. |
| 14:33 | Finished writing `copyconfig.service`. |
| 14:36 | Checked the size of the `boot` folder → too big to copy the whole thing; let's copy only `ip.md` and `config.txt` for now (or `*.txt`). |
| 14:39 | Finished writing `copyconfig.sh`. |
| 14:41 | Tried running the system service, but it didn't work → we had `User=pi`, which is a non-existent user. |
| 14:45 | Changed it to `stu3340` → ran it → it worked, but we saw that `/boot/config.txt` had no actual config in it. The contents are in `/boot/firmware/config.txt`. |
| 14:47 | Added `--allow-empty` to the commit command in the script so that it pushes even if the IP doesn't change → that way we know for sure that the Pi has booted. |
| 14:49 | Tested the service by restarting the Pi → it worked! |
| 14:51 | Made sure to copy `/boot/firmware/config`; mirrored the same structure in the user folder → added `boot/firmware`. |
| 14:55 | Just for fun: added a command that sends a notification on the Pi display saying that the updated IP has been pushed. (The UI probably won't be used again, but it's fun.) |
Note: code can be found in main folder's rpi/config folder
