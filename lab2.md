Manually copy a file from your Pi to your laptop using [SCP](https://man7.org/linux/man-pages/man1/scp.1.html). This is a quick and dirty way to move files around when there's no time for doing the whole Git spiel. \[CLI\]

* 1:48 – created “file” with touch command on Pi  
* 1:49 – found laptop IP address using ifconfig  
* 1:51 – scp file from Pi to laptop, encountered connection refused error  
  * scp file \[name\]@\[ip\]:/user/\[name\]  
* 1:52 – attempted debug by editing Mac laptop system settings, remote login on  
* 1:53 – debugging work, scp succeeded and moved file onto laptop

Write a (Bash) script using the above outline to copy your ip.md file to your laptop.

* 1:59 – wrote up bash script  
  * cd \~ && hostname \-I \> [ip.md](http://ip.md) && scp [ip.md](http://ip.md) \[name\]@\[ip\]:/user/\[name\]  
  * 2:00 – verified above command works as expected, copied ssh key over  
* 2:01 – looked into crontab documents to see how to run script/command every 10 minutes  
* 2:08 – tried setting up crontab using system-wide, failed, switched to user-wide  
  * /etc/crontab vs. crontab \-e   
* 2:11 – monitoring/verifying correctness using 1 minute cron and watch command  
* 2:13 – noted correct behavior, and that crontab runs at the start of every minute, not depending on the exact command time, changed back to 10 minutes