import os
import zipfile


def zip_directory(directory):
    """
    Zips all files in a directory.
    :param directory: The directory to zip.
    :type directory: str
    """
    zip_filename = f"{directory}.zip"
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, start=os.path.join(directory, '..')))


if __name__ == "__main__":
    user_defined_folder = input("Enter the folder name within the current directory: ")
    if not user_defined_folder:
        # Get the first subdirectory in the current directory that is not a hidden directory
        user_defined_folder = [d for d in os.listdir() if os.path.isdir(d) and not d.startswith('.')][0]
    if os.path.isdir(user_defined_folder):
        zip_directory(user_defined_folder)
        print(f"Processed and zipped the directory {user_defined_folder} successfully.")
    else:
        print("The specified directory does not exist.")
