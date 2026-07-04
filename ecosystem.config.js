// PM2 process definition for the DogeBox Reward Tracker.
//
//   pm2 start ecosystem.config.js
//   pm2 save
//   pm2 startup        # then run the printed command once
//
// Pins the project virtualenv interpreter, working directory and log files.
module.exports = {
  apps: [
    {
      name: "dogebox-reward-tracker",
      script: "main.py",
      interpreter: "./.venv/bin/python3",
      cwd: __dirname,
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
      max_memory_restart: "350M",
      out_file: "logs/pm2-out.log",
      error_file: "logs/pm2-error.log",
      merge_logs: true,
      time: true,
      env: {
        PYTHONUNBUFFERED: "1",
      },
    },
  ],
};
