sudo /home/wuzhenyu/anaconda3/bin/python -m batch_run \
  --domains all \
  --models none \
  --planner_executor_model gpt-4o uground7b \
  --model_sub_dir single_task \
  --config_file config/uground-gpt-linux_single.yaml
