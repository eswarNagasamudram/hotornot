from os import walk
mypath = "Juleo/video_official_dataset/"
filenames = next(walk(mypath), (None, None, []))[2]  # [] if no file
for name in filenames :
    print(name)