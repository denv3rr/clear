import runpy


def main() -> None:
    runpy.run_path("run.py", run_name="__main__")


if __name__ == "__main__":
    main()
