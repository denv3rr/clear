param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Args
)

python "$PSScriptRoot\clearctl.py" @Args
