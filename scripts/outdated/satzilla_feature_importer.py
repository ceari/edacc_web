import sys, tempfile, subprocess, os
sys.path.append("..")
from sqlalchemy.orm import joinedload_all
from edacc import models, config, constants

db = models.add_database(*config.DEFAULT_DATABASES[0])
TMP_DIR = '/tmp'
SATZILLA_FEATURE_SCRIPT = "featuresSAT12"


#instance_class = db.session.query(db.InstanceClass).options(joinedload_all('instances.properties')).filter_by(name=INSTANCE_CLASS).first()
property_by_name = dict()
for instance in db.session.query(db.Instance).options(joinedload_all('properties')):
    instance_path = os.path.join(TMP_DIR, instance.md5)
    with open(instance_path, 'wb') as instance_file:
        instance_file.write(instance.get_instance(db))

    features = subprocess.Popen([SATZILLA_FEATURE_SCRIPT, "-base", instance_path], stdout=subprocess.PIPE)
    feature_names = features.stdout.readline().strip().split(",")
    feature_values = features.stdout.readline().strip().split(",")
    features.wait()
    os.remove(instance_path)
    if not feature_names or not feature_values or len(feature_names) == 1:
        print "Couldn't compute features of instance " + instance.name
        continue

    for name, value in zip(feature_names, feature_values):
        if name not in property_by_name:
            property_by_name[name] = db.session.query(db.Property).filter_by(name=name).first()
            if not property_by_name[name]:
                raise Exception("Property " + repr(name) + " not found")

        instance_property = db.session.query(db.InstanceProperties).filter_by(instance=instance, property=property_by_name[name]).first()
        # check if instance doesn't have a value for this property yet
        if not instance_property:
            instance_property = db.InstanceProperties()
            instance_property.instance = instance
            instance_property.property = property_by_name[name]
        # in any case, update the value
        instance_property.value = value

    try:
        db.session.commit()
        print "Added features of instance " + instance.name
    except Exception as e:
        db.session.rollback()
        raise e
